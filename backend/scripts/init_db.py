"""Create all tables, load the demo profile, sync sources.yaml.  Run from backend/:  python scripts/init_db.py"""
import _path  # noqa: F401
from app import db

db.init_db()
con = db.connect()
print("tables:", [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table') ORDER BY name")])
print("profile:", db.get_profile(con)["name"], "| sources:", con.execute("SELECT COUNT(*) FROM sources WHERE enabled=1").fetchone()[0])
