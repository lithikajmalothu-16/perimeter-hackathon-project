"""Ingest sources from config/sources.yaml.
  python scripts/run_ingest.py                    every enabled source
  python scripts/run_ingest.py eni_cal launchgsu  only these ids
  python scripts/run_ingest.py --prefix prog_     only ids starting with prog_ (the program page for every major)"""
import sys
import time
import _path  # noqa: F401
from app import db
from app.agents import ingestion

db.init_db()
args = sys.argv[1:]
con = db.connect()
if args[:1] == ["--prefix"]:
    pre = args[1] if len(args) > 1 else ""
    ids = [r[0] for r in con.execute("SELECT id FROM sources WHERE enabled=1 AND id LIKE ? ORDER BY id", (pre + "%",)).fetchall()]
elif args:
    ids = args
else:
    ids = [r[0] for r in con.execute("SELECT id FROM sources WHERE enabled=1 ORDER BY id").fetchall()]
print(f"ingesting {len(ids)} source(s)…", flush=True)
ok = err = rows = 0
t0 = time.time()
for n, i in enumerate(ids, 1):
    r = ingestion.run_source(i, con)
    flag = "ERROR " + r["error"][:90] if r.get("error") else "ok"
    ok += not r.get("error"); err += bool(r.get("error")); rows += r["rows_new"] + r["rows_changed"]
    print(f"[{n}/{len(ids)}] {r['source_id']:<34} new={r['rows_new']:<3} changed={r['rows_changed']:<3} dropped={r['rows_dropped']:<3} alerts={r.get('alerts_created', 0):<2} {flag}", flush=True)
print(f"done in {time.time() - t0:.0f}s · {ok} ok · {err} errors · {rows} rows new/changed · resources in KB: "
      f"{con.execute('SELECT COUNT(*) FROM resources').fetchone()[0]}")
