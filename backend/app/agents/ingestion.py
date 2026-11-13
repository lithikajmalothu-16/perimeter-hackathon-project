"""Ingestion agent: the ONLY writer to `resources`.
fetch (allowlist) -> parse (rss | page | index) -> LLM extraction -> evidence-quote check -> content-hash diff -> upsert.
Every run is logged in ingestion_runs; the watcher runs right after."""
from __future__ import annotations
import hashlib
import json
import logging
import re
import sqlite3

from .. import db, llm
from ..ingest import extract as ex
from ..ingest import parse_html, parse_rss
from ..ingest.fetch import FetchError, fetch

log = logging.getLogger("pathfinder.ingestion")


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "item"


def row_hash(r: dict) -> str:
    keys = ["name", "type", "campus", "summary", "eligibility", "how_to_start", "contact_office", "contact_email",
            "contact_phone", "location_building", "location_room", "hours", "deadline", "event_start", "event_end"]
    return hashlib.sha256(json.dumps({k: r.get(k) for k in keys}, sort_keys=True, default=str).encode()).hexdigest()


def _rss_rows(src: dict, xml: str) -> tuple[list[dict], int]:
    rows, dropped = [], 0
    for it in parse_rss.parse(xml):
        if not it["title"]:
            dropped += 1
            continue
        campus = src["campus"]
        if "clarkston" in (it["location"] or "").lower():
            campus = ex.clamp_campus("clarkston", campus)
        rows.append({
            "name": it["title"], "type": "event", "campus": campus, "audience": "all_gsu",
            "topics": ex.guess_topics(f"{it['title']} {it['summary']} {src.get('label', '')}") or ["events"],
            "summary": it["summary"] or None, "how_to_start": "RSVP on the event page" if it["link"] else None,
            "contact_office": src.get("label"), "location_building": it["location"] or None,
            "event_start": it["event_start"], "event_end": it["event_end"],
            "evidence": it["title"],                 # the title is copied verbatim from the feed
            "source_url": it["link"] or src["url"],
        })
    return rows, dropped


def _page_rows(src: dict, final_url: str, html: str) -> tuple[list[dict], int, str]:
    text, links, title = parse_html.parse(html, final_url)
    rows, dropped, provider = ex.extract(text, final_url, src["campus"])
    for r in rows:
        r["source_url"] = final_url
    if src["kind"] == "index" and int(src.get("max_depth") or 0) >= 1:
        for link in links[:6]:                       # depth-1, same domain only
            try:
                u2, h2, _ = fetch(link)
                t2, _, _ = parse_html.parse(h2, u2)
                r2, d2, _ = ex.extract(t2, u2, src["campus"])
                for r in r2:
                    r["source_url"] = u2
                rows += r2
                dropped += d2
            except (FetchError, llm.LLMError) as e:
                log.info("index child skipped %s: %s", link, e)
    return rows, dropped, provider


def run_source(source_id: str, con: sqlite3.Connection | None = None) -> dict:
    """Fetch one source and upsert its rows. Never deletes rows: a failed fetch keeps the stored copy."""
    own = con is None
    con = con or db.connect()
    started = db.now_iso()
    cur = con.execute("INSERT INTO ingestion_runs (source_id, started_at) VALUES (?,?)", (source_id, started))
    run_id = cur.lastrowid
    con.commit()
    src = db.get_source(con, source_id)
    new = changed = dropped = 0
    error = None
    try:
        if not src:
            raise FetchError(f"unknown source {source_id}")
        final_url, body, _ = fetch(src["url"])
        page_hash = hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest()
        if src["kind"] == "rss":
            rows, dropped = _rss_rows(src, body)
        elif src["kind"] in ("page", "index"):
            rows, dropped, _ = _page_rows(src, final_url, body)
        else:
            raise FetchError(f"kind '{src['kind']}' not supported (HTML pages and RSS only)")
        now = db.now_iso()
        seen = set()
        for r in rows:
            rid = f"{source_id}:{slug(r['name'])}" + (f"-{r['event_start'][:10]}" if r.get("event_start") else "")
            if rid in seen:
                continue
            seen.add(rid)
            h = row_hash(r)
            old = con.execute("SELECT content_hash, first_seen_at FROM resources WHERE id=?", (rid,)).fetchone()
            status = "new" if not old else ("changed" if old["content_hash"] != h else "unchanged")
            new += status == "new"
            changed += status == "changed"
            db.upsert_resource(con, {**r, "id": rid, "source_id": source_id, "fetched_at": now, "content_hash": h,
                                     "origin": "agent", "status": status, "run_id": run_id,
                                     "first_seen_at": old["first_seen_at"] if old else now})
        status = "ok" if (new or changed or src.get("content_hash") != page_hash) else "unchanged"
        con.execute("UPDATE sources SET content_hash=?, last_run_at=?, last_status=?, last_error=NULL"
                    + (", last_changed_at=?" if (new or changed) else "") + " WHERE id=?",
                    (page_hash, now, status, *( [now] if (new or changed) else []), source_id))
    except (FetchError, llm.LLMError) as e:
        error = str(e)[:500]
        con.execute("UPDATE sources SET last_run_at=?, last_status='error', last_error=? WHERE id=?", (db.now_iso(), error, source_id))
    except Exception as e:                           # parser bugs must not kill the server
        log.exception("ingestion crashed for %s", source_id)
        error = f"{type(e).__name__}: {e}"[:500]
        con.execute("UPDATE sources SET last_run_at=?, last_status='error', last_error=? WHERE id=?", (db.now_iso(), error, source_id))
    con.execute("UPDATE ingestion_runs SET finished_at=?, rows_new=?, rows_changed=?, rows_dropped=?, error=? WHERE id=?",
                (db.now_iso(), new, changed, dropped, error, run_id))
    con.commit()
    run = dict(con.execute("SELECT * FROM ingestion_runs WHERE id=?", (run_id,)).fetchone())
    from . import watcher                            # the watcher always runs right after an ingestion run
    run["alerts_created"] = watcher.process_run(run_id, con)
    if own:
        con.close()
    return run


def refresh_source(source_id: str, con: sqlite3.Connection | None = None) -> dict:
    """Same pipeline, called by the router when rows are stale."""
    return run_source(source_id, con)


def run_all(con: sqlite3.Connection | None = None) -> list[dict]:
    own = con is None
    con = con or db.connect()
    ids = [r["id"] for r in con.execute("SELECT id FROM sources WHERE enabled=1 ORDER BY id").fetchall()]
    runs = [run_source(i, con) for i in ids]
    if own:
        con.close()
    return runs
