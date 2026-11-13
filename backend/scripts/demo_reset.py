"""Before the pitch: clear eni_cal rows + all alerts so "Run now" on eni_cal recreates them and fires the alert toast.
python scripts/demo_reset.py [source_id]   (default eni_cal)"""
import sys
import _path  # noqa: F401
from app import db

sid = sys.argv[1] if len(sys.argv) > 1 else "eni_cal"
db.init_db()
con = db.connect()
ids = [r[0] for r in con.execute("SELECT id FROM resources WHERE source_id=?", (sid,)).fetchall()]
for i in ids:
    con.execute("DELETE FROM resources_fts WHERE id=?", (i,))
con.execute("DELETE FROM resources WHERE source_id=?", (sid,))
con.execute("DELETE FROM alerts")
con.execute("UPDATE sources SET content_hash=NULL WHERE id=?", (sid,))
con.commit()
print(f"cleared {len(ids)} {sid} rows and all alerts. Now click Run now on {sid}.")
