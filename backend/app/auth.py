"""GSU email verification for the sign-up page. 6-digit code, hashed, 10-minute expiry, 5 tries, 30-second resend cooldown.
The code prints in the API console ([DEV] line). No email service is wired up for the hackathon demo."""
from __future__ import annotations
import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

from . import db

log = logging.getLogger("pathfinder.auth")
GSU_EMAIL = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@(?:student\.)?gsu\.edu$")
SECRET = secrets.token_hex(32)          # per server process; tokens expire on restart (fine for a demo)
MSG_EMAIL = "Use your GSU email, like name@student.gsu.edu."


def norm(email: str) -> str:
    return (email or "").strip().lower()


def valid(email: str) -> bool:
    e = norm(email)
    return bool(GSU_EMAIL.match(e)) and ".." not in e


def _h(code: str, email: str) -> str:
    return hashlib.sha256(f"{code}:{email}".encode()).hexdigest()


def send_code(email: str) -> dict:
    e = norm(email)
    if not valid(e):
        return {"ok": False, "error": MSG_EMAIL}
    con = db.connect()
    row = con.execute("SELECT last_sent_at FROM verification_codes WHERE email=?", (e,)).fetchone()
    if row and row["last_sent_at"] and (datetime.now(timezone.utc) - datetime.fromisoformat(row["last_sent_at"])).total_seconds() < 30:
        con.close()
        return {"ok": False, "error": "Code already sent. Check the API console (or wait 30 seconds to resend)."}
    code = f"{secrets.randbelow(1_000_000):06d}"
    exp = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    con.execute("""INSERT INTO verification_codes (email, code_hash, expires_at, attempts, last_sent_at) VALUES (?,?,?,0,?)
                   ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash, expires_at=excluded.expires_at, attempts=0,
                   last_sent_at=excluded.last_sent_at""", (e, _h(code, e), exp, db.now_iso()))
    con.commit(); con.close()
    print(f"\n[DEV] Pathfinder code for {e}: {code}\n", flush=True)
    return {"ok": True}


def check_code(email: str, code: str) -> dict:
    e = norm(email)
    if not valid(e):
        return {"ok": False, "error": MSG_EMAIL}
    if not re.fullmatch(r"\d{6}", (code or "").strip()):
        return {"ok": False, "error": "Enter the 6-digit code."}
    con = db.connect()
    row = con.execute("SELECT * FROM verification_codes WHERE email=?", (e,)).fetchone()
    try:
        if not row:
            return {"ok": False, "error": "Tap Send code first."}
        if row["attempts"] >= 5:
            return {"ok": False, "error": "Too many tries. Tap Send code for a new one."}
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            return {"ok": False, "error": "That code expired. Tap Send code for a new one."}
        if not hmac.compare_digest(row["code_hash"], _h(code.strip(), e)):
            con.execute("UPDATE verification_codes SET attempts=attempts+1 WHERE email=?", (e,)); con.commit()
            left = 4 - row["attempts"]
            return {"ok": False, "error": f"That code doesn't match. {left} {'try' if left == 1 else 'tries'} left." if left > 0 else "Too many tries. Tap Send code for a new one."}
        con.execute("DELETE FROM verification_codes WHERE email=?", (e,)); con.commit()
        return {"ok": True, "token": token_for(e)}
    finally:
        con.close()


def token_for(email: str) -> str:
    exp = int(time.time()) + 1800
    sig = hmac.new(SECRET.encode(), f"{email}|{exp}".encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def token_ok(email: str, token: str) -> bool:
    try:
        exp, sig = token.split(".", 1)
        good = hmac.new(SECRET.encode(), f"{norm(email)}|{exp}".encode(), hashlib.sha256).hexdigest()
        return int(exp) > time.time() and hmac.compare_digest(sig, good)
    except Exception:
        return False
