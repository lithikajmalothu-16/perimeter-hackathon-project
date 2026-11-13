"""Roadmap builder: turns verified resources from a chat answer into ordered steps the student can check off.
Every step must cite a resource id that was retrieved (same rule as the router's match check)."""
from __future__ import annotations
import json
import sqlite3

from .. import db, llm
from ..config import prompt

WHEN = ["This week", "Within 2 weeks", "This month", "This semester"]


def _brief(rows: list[dict]) -> str:
    keep = ["id", "name", "type", "campus", "summary", "how_to_start", "contact_office", "contact_email", "location_building", "event_start", "deadline"]
    return json.dumps([{k: r.get(k) for k in keep if r.get(k)} for r in rows], ensure_ascii=False)[:9000]


def build_roadmap(goal: str, resource_ids: list[str], profile: dict, con: sqlite3.Connection) -> dict | None:
    ids = list(dict.fromkeys(i for i in resource_ids if i))[:10]
    rows = [r for r in (db.get_resource(con, i) for i in ids) if r]
    if not rows:
        return None
    by_id = {r["id"]: r for r in rows}
    try:
        out, _ = llm.complete_json(
            prompt("roadmap").replace("{profile}", json.dumps({k: profile.get(k) for k in ["name", "campus_name", "major", "topics"]}))
            .replace("{goal}", goal[:300]).replace("{rows}", _brief(rows)),
            schema_hint='{"title": str, "steps": [{"title": str, "resource_id": str, "when": str}]}')
        title = (out.get("title") or " ".join(goal.split()[:6]))[:80]
        steps = [{"title": s["title"][:160], "resource_id": s["resource_id"], "when": s.get("when") if s.get("when") in WHEN else "This month"}
                 for s in (out.get("steps") or []) if isinstance(s, dict) and s.get("title") and s.get("resource_id") in by_id][:6]
    except llm.LLMError:
        title, steps = " ".join(goal.split()[:6]).rstrip(".,?!"), []
    if len(steps) < 2:                                           # deterministic fallback: one step per resource
        steps = [{"title": r.get("how_to_start") or f"Check out {r['name']}", "resource_id": r["id"], "when": WHEN[min(i, 3)]} for i, r in enumerate(rows[:5])]
    cur = con.execute("INSERT INTO student_roadmaps (title, goal, steps, created_at) VALUES (?,?,?,?)",
                      (title, goal[:300], json.dumps(steps), db.now_iso()))
    con.commit()
    return get(con, cur.lastrowid)


def get(con: sqlite3.Connection, rid: int) -> dict | None:
    r = con.execute("SELECT * FROM student_roadmaps WHERE id=?", (rid,)).fetchone()
    if not r:
        return None
    steps = json.loads(r["steps"] or "[]")
    for s in steps:
        s["resource"] = db.get_resource(con, s["resource_id"])
    return {"id": r["id"], "title": r["title"], "goal": r["goal"], "created_at": r["created_at"], "steps": steps}


def list_all(con: sqlite3.Connection) -> list[dict]:
    return [get(con, r["id"]) for r in con.execute("SELECT id FROM student_roadmaps ORDER BY id DESC").fetchall()]
