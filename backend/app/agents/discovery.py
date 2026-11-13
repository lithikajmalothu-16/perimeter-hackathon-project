"""Discovery agent: when the KB has nothing on a topic (e.g. "medicine"), find official gsu.edu pages live.
Gemini + Google Search grounding -> resolve redirect links -> keep gsu.edu only (checked in code) -> register each page as a
`disc_*` source -> run it through the SAME ingestion pipeline (fetch, LLM extract, verbatim evidence check, hash diff).
Every discovered URL is also logged in pending_sources so a human can approve it into sources.yaml later."""
from __future__ import annotations
import logging
import re
import sqlite3
from urllib.parse import urlparse

import httpx

from .. import db, llm
from ..config import settings
from ..ingest.fetch import allowed
from . import ingestion

log = logging.getLogger("pathfinder.discovery")
CAMPUS_HINT = {"clarkston": "The student is at Perimeter College's Clarkston campus.", "perimeter_all": "The student is at GSU Perimeter College.",
               "online": "The student takes Perimeter College classes online.", "atlanta_only": "The student is on the Atlanta campus."}


def _resolve(url: str) -> str | None:
    """Grounding links are vertexaisearch redirects; follow ONE hop to read the real target without fetching it."""
    if allowed(url):
        return url
    try:
        r = httpx.get(url, follow_redirects=False, timeout=8, headers={"User-Agent": settings.user_agent})
        loc = r.headers.get("location")
        return loc if loc and allowed(loc) else None
    except httpx.HTTPError:
        return None


def _sid(url: str) -> str:
    p = urlparse(url)
    return "disc_" + re.sub(r"[^a-z0-9]+", "_", (p.hostname or "").replace(".gsu.edu", "") + p.path.lower()).strip("_")[:50]


def discover(question: str, profile: dict, con: sqlite3.Connection, max_pages: int = 2) -> dict:
    """Returns {"sources": [ids ingested], "rows": n_new_rows, "urls": [...], "error": str|None}."""
    try:
        found, _ = llm.search_gsu(question, CAMPUS_HINT.get(profile.get("campus") or "", ""))
    except llm.LLMError as e:
        return {"sources": [], "rows": 0, "urls": [], "error": str(e)[:200]}
    urls: list[str] = []
    for f in found:
        u = _resolve(f["url"])
        if u and u.split("#")[0] not in urls and not re.search(r"\.(pdf|docx?|xlsx?)$", u, re.I):
            urls.append(u.split("#")[0])
            con.execute("INSERT OR IGNORE INTO pending_sources (url, title, query, found_at, status) VALUES (?,?,?,?, 'pending')",
                        (u, f.get("title") or "", question[:200], db.now_iso()))
        if len(urls) >= max_pages + 2:
            break
    con.commit()
    done, rows = [], 0
    for u in urls:
        if len(done) >= max_pages:
            break
        sid = _sid(u)
        if not db.get_source(con, sid):
            con.execute("INSERT INTO sources (id,url,kind,campus,every_hours,max_depth,enabled,label,origin) VALUES (?,?,?,?,?,?,?,?, 'discovery')",
                        (sid, u, "page", "gsu_wide", 24, 0, 1, (urlparse(u).hostname or "GSU").replace(".gsu.edu", "").upper() + " page"))
            con.commit()
        run = ingestion.run_source(sid, con)
        if not run.get("error"):
            done.append(sid)
            rows += run["rows_new"] + run["rows_changed"]
    return {"sources": done, "rows": rows, "urls": urls, "error": None if urls else "no gsu.edu pages found"}
