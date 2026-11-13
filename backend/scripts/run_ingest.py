"""Ingest every enabled source (or the ids given).  python scripts/run_ingest.py [source_id ...]"""
import sys
import _path  # noqa: F401
from app import db
from app.agents import ingestion

db.init_db()
ids = sys.argv[1:]
runs = [ingestion.run_source(i) for i in ids] if ids else ingestion.run_all()
for r in runs:
    flag = "ERROR " + r["error"] if r.get("error") else "ok"
    print(f"{r['source_id']:<26} new={r['rows_new']:<3} changed={r['rows_changed']:<3} dropped={r['rows_dropped']:<3} alerts={r.get('alerts_created', 0):<2} {flag}")
con = db.connect()
print("resources in KB:", con.execute("SELECT COUNT(*) FROM resources").fetchone()[0])
