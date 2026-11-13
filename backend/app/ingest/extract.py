"""LLM extraction of resource rows from page text + the evidence-quote check.
Rules (PRD 9): page text only, missing field = null, evidence must appear verbatim in the normalized page text
or the row is dropped, campus may be narrowed from the source default but never widened, contacts stay office-level
unless the page names a person with a role."""
from __future__ import annotations
import json
import re

from .. import llm
from ..config import prompt
from .parse_html import normalize

TYPES = {"office", "center", "program", "org", "opportunity", "event", "service"}
NARROW = {"gsu_wide": {"gsu_wide", "perimeter_all", "clarkston", "online", "atlanta_only"},
          "perimeter_all": {"perimeter_all", "clarkston", "online"}, "atlanta_only": {"atlanta_only"},
          "clarkston": {"clarkston"}, "online": {"online"}}
TOPIC_WORDS = {
    "business": ["business", "robinson", "marketing", "management", "finance", "accounting"],
    "entrepreneurship": ["entrepreneur", "startup", "start-up", "venture", "launch", "founder", "pitch", "innovation", "eni"],
    "transition": ["transition", "transfer", "atlanta campus", "bachelor", "move downtown"],
    "advising": ["advis", "advisor", "adviser", "hold", "registration"],
    "career": ["career", "internship", "job", "resume", "recruit", "employer"],
    "events": ["event", "workshop", "info session", "meetup", "night"],
    "clubs": ["club", "organization", "student org"],
    "international": ["international", "global", "ciber", "study abroad"],
    "financial_aid": ["financial aid", "scholarship", "fafsa", "grant"],
}


def guess_topics(text: str) -> list[str]:
    t = text.lower()
    return [k for k, ws in TOPIC_WORDS.items() if any(w in t for w in ws)]


def evidence_ok(evidence: str | None, page_norm: str) -> bool:
    if not evidence or len(evidence.strip()) < 8:
        return False
    return normalize(evidence) in page_norm


def clamp_campus(value: str | None, default: str) -> str:
    return value if value in NARROW.get(default, {default}) else default


def clean_row(r: dict, default_campus: str) -> dict:
    out = {k: (r.get(k) if r.get(k) not in ("", "null", "None", "N/A") else None) for k in
           ["name", "type", "audience", "summary", "eligibility", "how_to_start", "contact_office", "contact_email", "contact_phone",
            "location_building", "location_room", "hours", "deadline", "event_start", "event_end", "evidence"]}
    out["type"] = out["type"] if out["type"] in TYPES else "service"
    out["campus"] = clamp_campus(r.get("campus"), default_campus)
    t = r.get("topics") or []
    out["topics"] = [str(x).lower().strip() for x in t if str(x).strip()][:8] if isinstance(t, list) else []
    if not out["topics"]:
        out["topics"] = guess_topics(f"{out['name']} {out['summary']}")
    if out["contact_email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]{2,}$", out["contact_email"], re.I):
        out["contact_email"] = None
    return out


def extract(page_text: str, url: str, default_campus: str) -> tuple[list[dict], int, str]:
    """Returns (kept_rows, rows_dropped, provider). Raises llm.LLMError if no LLM is reachable."""
    text = page_text[:14000]
    data, provider = llm.complete_json(
        prompt("extract").replace("{url}", url).replace("{campus}", default_campus).replace("{page_text}", text),
        schema_hint='{"rows":[{"name":str,"type":"office|center|program|org|opportunity|event|service","campus":str,'
                    '"audience":"perimeter|atlanta|all_gsu","topics":[str],"summary":str,"eligibility":str|null,"how_to_start":str|null,'
                    '"contact_office":str|null,"contact_email":str|null,"contact_phone":str|null,"location_building":str|null,'
                    '"location_room":str|null,"hours":str|null,"deadline":"YYYY-MM-DD"|null,"event_start":"ISO"|null,'
                    '"event_end":"ISO"|null,"evidence":"exact sentence copied from the page"}]}',
        system="You extract structured facts from Georgia State University web pages. You never invent facts.")
    norm = normalize(page_text)
    kept, dropped = [], 0
    for r in (data.get("rows") or [])[:25]:
        if not isinstance(r, dict) or not r.get("name") or not evidence_ok(r.get("evidence"), norm):
            dropped += 1
            continue
        kept.append(clean_row(r, default_campus))
    return kept, dropped, provider
