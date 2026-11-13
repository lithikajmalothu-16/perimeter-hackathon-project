"""Watcher agent: after each ingestion run, match new/changed rows to the student profile and write alerts.
Rule (PRD 10): row status is new|changed, topic overlap with the profile >= 1, campus isn't atlanta_only unless the
row's topics include 'transition', and event rows need event_start >= now."""
from __future__ import annotations
import sqlite3

from .. import db


def matches_profile(row: dict, profile: dict) -> bool:
    topics = set(row.get("topics") or [])
    if not topics & set(profile.get("topics") or []):
        return False
    if row.get("campus") == "atlanta_only" and "transition" not in topics:
        return False
    if row.get("type") == "event" and (not row.get("event_start") or row["event_start"] < db.now_iso()):
        return False
    return True


def message_for(row: dict, source_label: str) -> str:
    kind = "event" if row.get("type") == "event" else row.get("type") or "resource"
    who = source_label or "GSU"
    return f"New {who} {kind} matches your interests: {row['name']}"


def process_run(run_id: int, con: sqlite3.Connection | None = None) -> int:
    own = con is None
    con = con or db.connect()
    profile = db.get_profile(con)
    rows = [db.resource_dict(r) for r in con.execute(
        "SELECT r.*, s.label AS source_label FROM resources r JOIN sources s ON s.id=r.source_id "
        "WHERE r.run_id=? AND r.status IN ('new','changed')", (run_id,)).fetchall()]
    created = 0
    for r in rows:
        if matches_profile(r, profile):
            cur = con.execute("INSERT OR IGNORE INTO alerts (profile_id, resource_id, message, created_at, read) VALUES (1,?,?,?,0)",
                              (r["id"], message_for(r, r.get("source_label")), db.now_iso()))
            created += cur.rowcount
    con.commit()
    if own:
        con.close()
    return created
