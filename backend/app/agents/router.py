"""Router / planner agent (PRD 8):
plan JSON -> FTS5 KB search -> live refetch of stale rows through the ingestion agent -> answer JSON
-> drop matches not in the retrieved set -> verify_grounded() -> response with a full trace."""
from __future__ import annotations
import json
import re
import time
from datetime import datetime, timedelta, timezone

from .. import db, llm
from ..config import DATA_DIR, prompt, settings
from . import ingestion
from .verify import verify_grounded

CAMPUS_RANK = {"clarkston": 0, "perimeter_all": 1, "online": 1, "gsu_wide": 2, "atlanta_only": 3}
CACHE = DATA_DIR / "demo_cache.json"


class Trace:
    def __init__(self):
        self.steps, self.t = [], time.time()

    def add(self, step: str, detail: str):
        now = time.time()
        self.steps.append({"step": step, "detail": detail, "ms": int((now - self.t) * 1000)})
        self.t = now


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", s.lower()).strip()


def _profile_brief(p: dict) -> str:
    return json.dumps({k: p.get(k) for k in ["name", "campus", "pathway_id", "credits", "work_hours", "holds", "interests", "topics"]})


def _rows_brief(rows: list[dict]) -> str:
    keep = ["id", "name", "type", "campus", "topics", "summary", "eligibility", "how_to_start", "contact_office", "contact_email",
            "contact_phone", "location_building", "location_room", "hours", "deadline", "event_start", "source_url"]
    return json.dumps([{k: r.get(k) for k in keep if r.get(k)} for r in rows], ensure_ascii=False)[:14000]


def _is_stale(r: dict) -> bool:
    try:
        return datetime.fromisoformat(r["fetched_at"]) < datetime.now(timezone.utc) - timedelta(hours=settings.stale_hours)
    except Exception:
        return True


def _retrieve(con, plan: dict, message: str, profile: dict) -> list[dict]:
    hits: dict[str, dict] = {}
    for q in (plan.get("searches") or [message])[:4] + [message]:
        for i, r in enumerate(db.search(con, q, 20)):
            if r["id"] not in hits or r["score"] < hits[r["id"]]["score"]:
                hits[r["id"]] = r
    ranked = sorted(hits.values(), key=lambda r: r["score"])[:10]        # top 10 by relevance (bm25: lower is better)
    if plan.get("needs_events", True):                                    # + 3 soonest upcoming events
        for e in db.upcoming_events(con, 3, plan.get("topics") or profile.get("topics") or []):
            if e["id"] not in {r["id"] for r in ranked}:
                e["score"] = 0.0
                ranked.append(e)
    return sorted(ranked, key=lambda r: CAMPUS_RANK.get(r.get("campus"), 2))  # then campus ranking (stable)


def _fallback_plan(message: str, profile: dict) -> dict:
    from ..ingest.extract import guess_topics
    topics = guess_topics(message) or profile.get("topics") or []
    return {"intent": "find resources", "searches": [message, " ".join(topics)], "needs_events": "advis" not in message.lower(), "topics": topics}


def _fallback_answer(rows: list[dict], topics: list[str] | None = None) -> dict:
    t = set(topics or [])
    top = sorted(rows, key=lambda r: -len(t & set(r.get("topics") or [])))[:3] if t else rows[:3]
    if not top:
        return {"answer_text": "I couldn't find a verified GSU resource for that yet. Try the Sources tab to refresh the data.", "matches": []}
    names = ", ".join(r["name"] for r in top)
    return {"answer_text": f"Here are the verified GSU resources that fit best: {names}.",
            "matches": [{"resource_id": r["id"], "why": (r.get("summary") or r["name"])[:180],
                         "first_step": r.get("how_to_start") or (f"Contact {r['contact_office']}" if r.get("contact_office") else "Open the source page")} for r in top]}


def handle(message: str, history: list[dict], profile: dict) -> dict:
    tr = Trace()
    con = db.connect()
    try:
        llm_on = llm.available()
        # 1. plan
        try:
            plan, prov = llm.complete_json(
                prompt("plan").replace("{profile}", _profile_brief(profile)).replace("{message}", message)
                .replace("{history}", json.dumps(history[-6:])),
                schema_hint='{"intent": str, "searches": [str], "needs_events": bool, "topics": [str]}')
            tr.add("plan", f"{prov}: {plan.get('intent', '')} · searches: {', '.join(plan.get('searches') or [])}")
        except llm.LLMError as e:
            plan = _fallback_plan(message, profile)
            tr.add("plan", "keyword plan (no LLM reachable)" if not llm_on else f"LLM failed, keyword plan: {str(e)[:120]}")

        # 2. KB search
        rows = _retrieve(con, plan, message, profile)
        tr.add("search", f"FTS5 · {len(rows)} rows · top: {', '.join(r['name'] for r in rows[:3]) or 'none'}")

        # 3. live refetch of stale rows (only sources whose last fetch worked; blocked sources show the stored copy)
        stale_sources = []
        for r in rows[:5]:
            if _is_stale(r) and r["source_id"] not in stale_sources:
                stale_sources.append(r["source_id"])
        for sid in stale_sources:
            src = db.get_source(con, sid) or {}
            if src.get("last_status") in ("ok", "unchanged"):
                run = ingestion.refresh_source(sid, con)
                if run.get("error"):
                    tr.add("refetch", f"live fetch failed for {sid}, using copy from {(src.get('last_run_at') or '')[:10]}")
                else:
                    tr.add("refetch", f"refetched {sid}: {run['rows_new']} new, {run['rows_changed']} changed")
            else:
                tr.add("refetch", f"{sid} skipped (last status {src.get('last_status')}), using copy from {(src.get('last_run_at') or '')[:10]}")
        if stale_sources:
            rows = _retrieve(con, plan, message, profile)

        # 4. answer
        cached = _cache_lookup(message)
        try:
            ans, prov = llm.complete_json(
                prompt("answer").replace("{profile}", _profile_brief(profile)).replace("{message}", message).replace("{rows}", _rows_brief(rows[:13])),
                schema_hint='{"answer_text": str, "matches": [{"resource_id": str, "why": str, "first_step": str}]}')
            tr.add("answer", f"{prov}: {len(ans.get('matches') or [])} matches proposed")
        except llm.LLMError as e:
            if cached and settings.demo_fallback:
                tr.add("answer", "both LLMs failed · served cached demo answer")
                cached["trace"] = tr.steps + [{"step": "cache", "detail": "cached", "ms": 0}]
                return cached
            ans = _fallback_answer(rows, plan.get("topics") or [])
            tr.add("answer", "top search hits (no LLM reachable)" if not llm_on else f"LLM failed, top hits used: {str(e)[:120]}")

        # 5. drop matches whose resource_id wasn't retrieved
        by_id = {r["id"]: r for r in rows}
        matches, dropped = [], 0
        for m in (ans.get("matches") or [])[:3]:
            r = by_id.get(m.get("resource_id"))
            if not r:
                dropped += 1
                continue
            matches.append({"resource": {k: v for k, v in r.items() if k != "score"}, "why": m.get("why") or "",
                            "first_step": m.get("first_step") or r.get("how_to_start") or "Open the source page"})
        if dropped:
            tr.add("match-check", f"dropped {dropped} match(es) not in the retrieved set")

        # 6. groundedness
        cited = [m["resource"] for m in matches] or rows[:5]
        v = verify_grounded(ans.get("answer_text") or "", cited)
        tr.add("verify", f"{v['checker']}: " + ("all sentences supported" if v["grounded"] else f"removed {len(v['unsupported'])} sentence(s)"))
        return {"answer": v["answer"] or "Here's what I found in GSU's verified resources.", "matches": matches, "trace": tr.steps,
                "verification": {"checker": v["checker"], "removed_sentences": v["unsupported"]}}
    finally:
        con.close()


def _cache_lookup(message: str) -> dict | None:
    if not CACHE.exists():
        return None
    try:
        data = json.loads(CACHE.read_text(encoding="utf-8"))
        return data.get(_norm(message))
    except Exception:
        return None


def save_to_cache(message: str, response: dict) -> None:
    data = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    data[_norm(message)] = response
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(data, indent=1), encoding="utf-8")
