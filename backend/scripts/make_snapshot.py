"""Copy the local KB into data/seed_snapshot.db for deploys, WITHOUT personal data.
Keeps: resources, FTS index, sources, ingestion_runs. Resets the profile to the demo student and clears
codes, alerts, chat roadmaps and pending discoveries.   python scripts/make_snapshot.py"""
import shutil
import sqlite3
import _path  # noqa: F401
from app import db
from app.config import load_demo_profile, settings

db.init_db()
src = sqlite3.connect(settings.database_path)
src.execute("PRAGMA wal_checkpoint(FULL)")
src.close()
out = db.SNAPSHOT
out.unlink(missing_ok=True)
shutil.copy(settings.database_path, out)
con = sqlite3.connect(out)
for t in ["verification_codes", "alerts", "student_roadmaps", "pending_sources"]:
    con.execute(f"DELETE FROM {t}")
con.commit(); con.close()
s = sqlite3.connect(out); s.row_factory = sqlite3.Row
db.save_profile({**load_demo_profile(), "email": None, "email_verified": False, "major": None, "campus_name": "Clarkston"}, s)
s.execute("PRAGMA journal_mode=DELETE"); s.commit()
n = s.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
s.execute("VACUUM"); s.close()
print(f"wrote {out} with {n} resources (profile reset to demo, no emails/codes/alerts)")
