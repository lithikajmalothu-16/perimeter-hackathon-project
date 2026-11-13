"""verify_grounded(): removes answer sentences the retrieved rows don't support. Gemini/Groq through llm();
with no LLM reachable it falls back to a lexical check (each sentence's key words must appear in the rows)."""
from __future__ import annotations
import json
import re

from .. import llm
from ..config import prompt

SPLIT = re.compile(r"(?<=[.!?])\s+")
FILLER = re.compile(r"^(here('| i)s|good news|great|you('ve| have) got|let's|start here|a few options)", re.I)


def _rows_brief(rows: list[dict]) -> str:
    keep = ["id", "name", "type", "campus", "summary", "eligibility", "how_to_start", "contact_office", "contact_email",
            "contact_phone", "location_building", "hours", "deadline", "event_start", "evidence"]
    return json.dumps([{k: r.get(k) for k in keep if r.get(k)} for r in rows], ensure_ascii=False)[:12000]


def _lexical(answer: str, rows: list[dict]) -> list[str]:
    corpus = " ".join(" ".join(str(v) for v in r.values() if v) for r in rows).lower()
    bad = []
    for s in SPLIT.split(answer.strip()):
        words = [w for w in re.findall(r"[A-Za-z][A-Za-z\-']{3,}", s) if w[0].isupper() or len(w) > 7]
        if words and not FILLER.match(s) and sum(w.lower() in corpus for w in words) / len(words) < 0.5:
            bad.append(s)
    return bad


def verify_grounded(answer: str, rows: list[dict]) -> dict:
    """Returns {grounded, unsupported, checker, answer} where answer has the unsupported sentences removed."""
    if not answer.strip():
        return {"grounded": True, "unsupported": [], "checker": "none", "answer": answer}
    checker = "lexical"
    try:
        out, checker = llm.complete_json(prompt("verify").replace("{answer}", answer).replace("{rows}", _rows_brief(rows)),
                                         schema_hint='{"unsupported": [str]}',
                                         system="You are a strict fact checker. You only judge support, you never rewrite.")
        unsupported = [s for s in (out.get("unsupported") or []) if isinstance(s, str) and s.strip() and s.strip() in answer]
    except llm.LLMError:
        unsupported = _lexical(answer, rows)
    cleaned = answer
    for s in unsupported:
        cleaned = cleaned.replace(s, "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return {"grounded": not unsupported, "unsupported": unsupported, "checker": checker, "answer": cleaned}
