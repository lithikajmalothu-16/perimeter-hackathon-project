"""GSU email check for the sign-up page. Only @student.gsu.edu and @gsu.edu addresses are accepted.
(The 6-digit code step was removed: codes could only be read from the server log, which visitors can't see.)"""
from __future__ import annotations
import re

GSU_EMAIL = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?@(?:student\.)?gsu\.edu$")
MSG_EMAIL = "Use your GSU email, like name@student.gsu.edu."


def norm(email: str) -> str:
    return (email or "").strip().lower()


def valid(email: str) -> bool:
    e = norm(email)
    return bool(GSU_EMAIL.match(e)) and ".." not in e
