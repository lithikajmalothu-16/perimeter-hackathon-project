"""RSS/Atom (calendar.gsu.edu Localist feeds) -> event rows. Deterministic: no LLM needed for events."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from html import unescape

import feedparser

TAGS = re.compile(r"<[^>]+>")
WS = re.compile(r"\s+")


def clean(s: str | None) -> str:
    return WS.sub(" ", unescape(TAGS.sub(" ", s or ""))).strip()


def _dt(entry, *keys) -> str | None:
    for k in keys:
        v = entry.get(k)
        if v and hasattr(v, "tm_year"):
            return datetime(*v[:6], tzinfo=timezone.utc).isoformat()
    return None


def parse(xml: str) -> list[dict]:
    feed = feedparser.parse(xml)
    out = []
    for e in feed.entries:
        title = clean(e.get("title"))
        if not title:
            continue
        desc = clean(e.get("summary") or e.get("description"))
        # Localist puts "Starts/Ends" in namespaced fields; fall back to published date
        start = _dt(e, "ev_startdate_parsed", "start_parsed", "published_parsed", "updated_parsed")
        end = _dt(e, "ev_enddate_parsed", "end_parsed")
        loc = clean(e.get("ev_location") or e.get("location") or "")
        if not loc:
            m = re.search(r"(?:Location|Where):\s*([^|\n]{3,80})", desc)
            loc = m.group(1).strip() if m else ""
        out.append({"title": title, "link": e.get("link"), "summary": desc[:600], "event_start": start, "event_end": end,
                    "location": loc, "raw_text": f"{title} {desc} {loc}"})
    return out
