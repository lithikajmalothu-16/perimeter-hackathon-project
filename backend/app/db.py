"""SQLite connection, schema (PRD section 9), FTS5 index and queries."""
from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Iterable

from .config import settings, load_sources, load_demo_profile

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
  id INTEGER PRIMARY KEY, name TEXT, campus TEXT, pathway_id TEXT, credits INTEGER, work_hours INTEGER,
  holds TEXT, interests TEXT, topics TEXT, updated_at TEXT
);
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, url TEXT NOT NULL, kind TEXT NOT NULL, campus TEXT NOT NULL, every_hours REAL, max_depth INTEGER DEFAULT 0,
  enabled INTEGER DEFAULT 1, label TEXT, content_hash TEXT, last_run_at TEXT, last_changed_at TEXT, last_status TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS resources (
  id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id), name TEXT NOT NULL,
  type TEXT CHECK (type IN ('office','center','program','org','opportunity','event','service')),
  campus TEXT CHECK (campus IN ('clarkston','perimeter_all','online','gsu_wide','atlanta_only')),
  audience TEXT, topics TEXT, summary TEXT, eligibility TEXT, how_to_start TEXT,
  contact_office TEXT, contact_email TEXT, contact_phone TEXT, location_building TEXT, location_room TEXT, hours TEXT,
  deadline TEXT, event_start TEXT, event_end TEXT, evidence TEXT NOT NULL, source_url TEXT, fetched_at TEXT,
  content_hash TEXT, origin TEXT DEFAULT 'agent', status TEXT, first_seen_at TEXT, run_id INTEGER
);
CREATE VIRTUAL TABLE IF NOT EXISTS resources_fts USING fts5(
  id UNINDEXED, name, summary, topics, eligibility, how_to_start, tokenize = 'porter unicode61'
);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, profile_id INTEGER, resource_id TEXT, message TEXT, created_at TEXT, read INTEGER DEFAULT 0,
  UNIQUE (profile_id, resource_id)
);
CREATE TABLE IF NOT EXISTS student_roadmaps (               -- roadmaps built from chat answers; every step cites a resource id
  id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, goal TEXT, steps TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS pending_sources (                -- URLs found by the discovery agent, awaiting human approval
  url TEXT PRIMARY KEY, title TEXT, query TEXT, found_at TEXT, status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS verification_codes (
  email TEXT PRIMARY KEY, code_hash TEXT NOT NULL, expires_at TEXT NOT NULL, attempts INTEGER DEFAULT 0, last_sent_at TEXT
);
CREATE TABLE IF NOT EXISTS ingestion_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, source_id TEXT, started_at TEXT, finished_at TEXT,
  rows_new INTEGER DEFAULT 0, rows_changed INTEGER DEFAULT 0, rows_dropped INTEGER DEFAULT 0, error TEXT
);
"""

RESOURCE_FIELDS = ["id", "source_id", "name", "type", "campus", "audience", "topics", "summary", "eligibility", "how_to_start",
                   "contact_office", "contact_email", "contact_phone", "location_building", "location_room", "hours", "deadline",
                   "event_start", "event_end", "evidence", "source_url", "fetched_at", "content_hash", "origin", "status",
                   "first_seen_at", "run_id"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.database_path, check_same_thread=False, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


MIGRATIONS = [  # columns added after the first release; ALTER fails harmlessly if they already exist
    "ALTER TABLE profile ADD COLUMN email TEXT", "ALTER TABLE profile ADD COLUMN email_verified INTEGER DEFAULT 0",
    "ALTER TABLE profile ADD COLUMN major TEXT", "ALTER TABLE profile ADD COLUMN campus_name TEXT",
    "ALTER TABLE sources ADD COLUMN origin TEXT DEFAULT 'config'",
]


def init_db() -> None:
    """Create tables, run migrations, load the demo profile, sync sources.yaml into the sources table."""
    with connect() as con:
        con.executescript(SCHEMA)
        for m in MIGRATIONS:
            try:
                con.execute(m)
            except sqlite3.OperationalError:
                pass
        if not con.execute("SELECT 1 FROM profile WHERE id=1").fetchone():
            save_profile(load_demo_profile(), con)
        sync_sources(con)


def sync_sources(con: sqlite3.Connection) -> None:
    cfg = load_sources()
    ids = []
    for s in cfg.get("sources", []):
        ids.append(s["id"])
        con.execute(
            """INSERT INTO sources (id,url,kind,campus,every_hours,max_depth,enabled,label) VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET url=excluded.url, kind=excluded.kind, campus=excluded.campus,
               every_hours=excluded.every_hours, max_depth=excluded.max_depth, enabled=excluded.enabled, label=excluded.label""",
            (s["id"], s["url"], s["kind"], s["campus"], s.get("every_hours", 24), s.get("max_depth", 0),
             1 if s.get("enabled", True) else 0, s.get("label", s["id"])),
        )
    if ids:  # sources removed from the YAML are disabled, never deleted (their rows keep their citations)
        con.execute(f"UPDATE sources SET enabled=0 WHERE id NOT LIKE 'disc_%' AND id NOT IN ({','.join('?' * len(ids))})", ids)


# ------------------------------------------------------------------ profile
def _row_to_profile(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["holds"] = json.loads(d.get("holds") or "[]")
    d["topics"] = json.loads(d.get("topics") or "[]")
    return d


def get_profile(con: sqlite3.Connection | None = None) -> dict:
    own = con is None
    con = con or connect()
    try:
        r = con.execute("SELECT * FROM profile WHERE id=1").fetchone()
        return _row_to_profile(r) if r else {}
    finally:
        if own:
            con.close()


def save_profile(p: dict, con: sqlite3.Connection | None = None) -> dict:
    own = con is None
    con = con or connect()
    try:
        con.execute(
            """INSERT INTO profile (id,name,campus,pathway_id,credits,work_hours,holds,interests,topics,updated_at,email,email_verified,major,campus_name)
               VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name, campus=excluded.campus,
               pathway_id=excluded.pathway_id, credits=excluded.credits, work_hours=excluded.work_hours, holds=excluded.holds,
               interests=excluded.interests, topics=excluded.topics, updated_at=excluded.updated_at, email=excluded.email,
               email_verified=excluded.email_verified, major=excluded.major, campus_name=excluded.campus_name""",
            (p.get("name"), p.get("campus"), p.get("pathway_id"), p.get("credits"), p.get("work_hours"),
             json.dumps(p.get("holds", [])), p.get("interests", ""), json.dumps(p.get("topics", [])), now_iso(),
             p.get("email"), 1 if p.get("email_verified") else 0, p.get("major"), p.get("campus_name")),
        )
        if own:
            con.commit()
        return get_profile(con)
    finally:
        if own:
            con.close()


# ------------------------------------------------------------------ resources
def resource_dict(r: sqlite3.Row | dict) -> dict:
    d = dict(r)
    d["topics"] = json.loads(d.get("topics") or "[]") if isinstance(d.get("topics"), str) else (d.get("topics") or [])
    return d


def get_resource(con: sqlite3.Connection, rid: str) -> dict | None:
    r = con.execute("SELECT * FROM resources WHERE id=?", (rid,)).fetchone()
    return resource_dict(r) if r else None


def upsert_resource(con: sqlite3.Connection, row: dict) -> None:
    vals = {k: row.get(k) for k in RESOURCE_FIELDS}
    vals["topics"] = json.dumps(row.get("topics") or [])
    cols = ",".join(RESOURCE_FIELDS)
    marks = ",".join("?" * len(RESOURCE_FIELDS))
    updates = ",".join(f"{k}=excluded.{k}" for k in RESOURCE_FIELDS if k not in ("id", "first_seen_at"))
    con.execute(f"INSERT INTO resources ({cols}) VALUES ({marks}) ON CONFLICT(id) DO UPDATE SET {updates}",
                [vals[k] for k in RESOURCE_FIELDS])
    con.execute("DELETE FROM resources_fts WHERE id=?", (row["id"],))
    con.execute("INSERT INTO resources_fts (id,name,summary,topics,eligibility,how_to_start) VALUES (?,?,?,?,?,?)",
                (row["id"], row.get("name") or "", row.get("summary") or "", " ".join(row.get("topics") or []),
                 row.get("eligibility") or "", row.get("how_to_start") or ""))


def fts_query(text: str) -> str:
    """Turn free text into a safe FTS5 OR query with prefix matching."""
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "at", "for", "my", "i", "me", "is", "it", "do", "what",
            "where", "who", "how", "should", "can", "with", "about", "want", "real", "start", "into", "turn", "mean", "talk"}
    words = [w for w in "".join(c.lower() if c.isalnum() else " " for c in text).split() if len(w) > 2 and w not in stop]
    return " OR ".join(f'"{w}"*' for w in dict.fromkeys(words)) or '""'


def search(con: sqlite3.Connection, text: str, limit: int = 20) -> list[dict]:
    q = fts_query(text)
    if q == '""':
        return []
    rows = con.execute(
        """SELECT r.*, bm25(resources_fts) AS score FROM resources_fts JOIN resources r ON r.id = resources_fts.id
           WHERE resources_fts MATCH ? ORDER BY score LIMIT ?""", (q, limit)).fetchall()
    return [resource_dict(r) for r in rows]


def upcoming_events(con: sqlite3.Connection, limit: int = 3, topics: Iterable[str] = ()) -> list[dict]:
    rows = con.execute("SELECT * FROM resources WHERE type='event' AND event_start >= ? ORDER BY event_start LIMIT 50",
                       (now_iso(),)).fetchall()
    out = [resource_dict(r) for r in rows]
    t = set(topics)
    if t:
        out.sort(key=lambda r: (0 if t & set(r["topics"]) else 1, r["event_start"] or ""))
    return out[:limit]


def list_resources(con: sqlite3.Connection, topic: str | None = None, campus: str | None = None, type_: str | None = None) -> list[dict]:
    sql, args = "SELECT * FROM resources WHERE 1=1", []
    if campus:
        sql += " AND campus=?"; args.append(campus)
    if type_:
        sql += " AND type=?"; args.append(type_)
    rows = [resource_dict(r) for r in con.execute(sql + " ORDER BY fetched_at DESC", args).fetchall()]
    return [r for r in rows if not topic or topic in r["topics"]]


def rows_for_source(con: sqlite3.Connection, source_id: str, limit: int = 5) -> list[dict]:
    rows = con.execute("SELECT * FROM resources WHERE source_id=? ORDER BY CASE type WHEN 'event' THEN 1 ELSE 0 END, fetched_at DESC LIMIT ?",
                       (source_id, limit)).fetchall()
    return [resource_dict(r) for r in rows]


# ------------------------------------------------------------------ sources + runs
def list_sources(con: sqlite3.Connection) -> list[dict]:
    out = []
    for s in con.execute("SELECT * FROM sources ORDER BY enabled DESC, id").fetchall():
        d = dict(s)
        run = con.execute("SELECT * FROM ingestion_runs WHERE source_id=? ORDER BY id DESC LIMIT 1", (s["id"],)).fetchone()
        d["last_run"] = dict(run) if run else None
        d["row_count"] = con.execute("SELECT COUNT(*) FROM resources WHERE source_id=?", (s["id"],)).fetchone()[0]
        out.append(d)
    return out


def get_source(con: sqlite3.Connection, sid: str) -> dict | None:
    r = con.execute("SELECT * FROM sources WHERE id=?", (sid,)).fetchone()
    return dict(r) if r else None


def kb_stats(con: sqlite3.Connection) -> dict[str, Any]:
    return {
        "resources": con.execute("SELECT COUNT(*) FROM resources").fetchone()[0],
        "sources_ok": con.execute("SELECT COUNT(*) FROM sources WHERE enabled=1 AND last_status IN ('ok','unchanged')").fetchone()[0],
        "sources": con.execute("SELECT COUNT(*) FROM sources WHERE enabled=1").fetchone()[0],
        "last_run_at": con.execute("SELECT MAX(last_run_at) FROM sources").fetchone()[0],
        "discovered": con.execute("SELECT COUNT(*) FROM sources WHERE id LIKE 'disc_%'").fetchone()[0],
    }
