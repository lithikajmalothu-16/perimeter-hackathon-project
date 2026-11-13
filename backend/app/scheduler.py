"""Background refresh (APScheduler). Off unless SCHEDULER_ENABLED=1; the Sources page "Run now" is the demo path.
Each enabled source runs on its own every_hours (calendars 3h, pages 24h)."""
from __future__ import annotations
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from . import db
from .agents import ingestion

log = logging.getLogger("pathfinder.scheduler")
_sched: BackgroundScheduler | None = None


def start() -> BackgroundScheduler | None:
    global _sched
    if _sched:
        return _sched
    _sched = BackgroundScheduler(timezone="America/New_York", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 600})
    con = db.connect()
    for s in con.execute("SELECT id, every_hours FROM sources WHERE enabled=1").fetchall():
        hours = float(s["every_hours"] or 24)
        _sched.add_job(ingestion.run_source, "interval", hours=hours, args=[s["id"]], id=f"ingest:{s['id']}", replace_existing=True)
        log.info("scheduled %s every %sh", s["id"], hours)
    con.close()
    _sched.start()
    return _sched


def stop() -> None:
    global _sched
    if _sched:
        _sched.shutdown(wait=False)
        _sched = None
