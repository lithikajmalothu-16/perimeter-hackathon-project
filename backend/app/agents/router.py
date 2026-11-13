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
from . import discovery, ingestion
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
    if plan.get("needs_events", True):                                    # + up to 3 soonest upcoming events ON THIS TOPIC
        terms = _terms(plan, message)
        for e in db.upcoming_events(con, 12, plan.get("topics") or []):
            text = f"{e.get('name')} {e.get('summary')} {' '.join(e.get('topics') or [])}".lower()
            if e["id"] not in {r["id"] for r in ranked} and (not terms or any(t[:6] in text for t in terms)):
                e["score"] = 0.0
                ranked.append(e)
                if sum(1 for r in ranked if r.get("score") == 0.0) >= 3:
                    break
    cname = (profile.get("campus_name") or "").lower()

    def campus_key(r: dict) -> tuple:
        here = 0 if cname and cname in f"{r.get('location_building')} {r.get('summary')} {r.get('name')}".lower() else 1
        return (here, CAMPUS_RANK.get(r.get("campus"), 2))
    return sorted(ranked, key=campus_key)                                 # the student's own campus first, then campus ranking


STOP = {"what", "where", "when", "which", "with", "want", "start", "about", "does", "mean", "talk", "need", "help", "find",
        "should", "could", "would", "there", "their", "into", "from", "have", "real", "like", "more", "some", "this", "that",
        "interested", "interest", "right", "now", "campus", "gsu", "georgia", "state", "university", "perimeter", "student",
        "students", "resources", "resource", "send", "show", "give", "tell", "looking", "options", "things", "anything",
        "something", "please", "thanks", "okay", "also", "just", "really", "good", "best", "college", "today", "here"}


def _terms(plan: dict, message: str) -> list[str]:
    """Topic words a relevant row must mention. The planner's must_mention wins; message words are the fallback."""
    t = [w.lower().strip() for w in (plan.get("must_mention") or []) if isinstance(w, str) and len(w.strip()) > 2 and w.lower() not in STOP]
    if not t:
        t = [w for w in re.findall(r"[a-z][a-z\-]{3,}", message.lower()) if w not in STOP]
    return list(dict.fromkeys(t))[:6]


def _covered(rows: list[dict], plan: dict, message: str) -> bool:
    """Does the KB actually have something on this topic? At least one top row must mention a key term."""
    terms = _terms(plan, message)
    if not terms:
        return bool(rows)
    for r in rows[:6]:
        text = " ".join(str(r.get(k) or "") for k in ("name", "summary", "eligibility", "how_to_start")).lower() + " " + " ".join(r.get("topics") or [])
        if any(t[:6] in text for t in terms):
            return True
    return False


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
                schema_hint='{"intent": str, "searches": [str], "needs_events": bool, "topics": [str], "must_mention": [str]}')
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

        # 3b. discovery: the curated KB has nothing on this topic -> find official gsu.edu pages live, verify them, add them
        discovered = False
        unverified: list[dict] = []

        def run_discovery(reason: str):
            nonlocal rows, discovered, unverified
            discovered = True
            if not (settings.gemini_api_key or settings.groq_api_key):
                tr.add("discover", f"{reason}; live discovery needs GEMINI_API_KEY or GROQ_API_KEY")
                return
            topic = " ".join(plan.get("searches") or [])[:120] or message
            tr.add("discover", f"{reason} · searching gsu.edu live for: {topic}")
            d = discovery.discover(f"{message} ({topic})", profile, con)
            unverified = d.get("unverified") or []
            if d["sources"]:
                tr.add("discover", f"found {len(d['urls'])} gsu.edu page(s), verified {d['rows']} row(s) from: {', '.join(d['sources'])}")
                rows = _retrieve(con, plan, message, profile)
            else:
                err = d["error"] or "pages failed the evidence check"
                if "429" in err or "RESOURCE_EXHAUSTED" in err or "quota" in err.lower():
                    err = "search quota used up on Gemini and Groq right now; wait a minute or use another key"
                tr.add("discover", f"nothing usable found ({err[:160]})")

        if not _covered(rows, plan, message):
            run_discovery(f"no verified rows about '{', '.join(_terms(plan, message)[:3]) or message[:40]}' yet")
        if not _covered(rows, plan, message):
            # still nothing on this topic: only pass rows that actually mention it, so the answer says "nothing yet"
            # instead of matching an unrelated card (e.g. a CleanTech internship for "medicine")
            terms = _terms(plan, message)
            rows = [r for r in rows if any(t[:6] in f"{r.get('name')} {r.get('summary')} {' '.join(r.get('topics') or [])}".lower() for t in terms)]
            tr.add("filter", f"kept {len(rows)} row(s) that mention: {', '.join(terms[:4])}")

        # 4. answer (if it comes back empty and we haven't searched live yet, discover and answer again)
        cached = _cache_lookup(message)

        def answer():
            return llm.complete_json(
                prompt("answer").replace("{profile}", _profile_brief(profile)).replace("{message}", message).replace("{rows}", _rows_brief(rows[:13])),
                schema_hint='{"answer_text": str, "matches": [{"resource_id": str, "why": str, "first_step": str}]}')
        try:
            ans, prov = answer()
            tr.add("answer", f"{prov}: {len(ans.get('matches') or [])} matches proposed")
            if not ans.get("matches") and not discovered and rows:
                run_discovery("answer had no matching resources")
                ans, prov = answer()
                tr.add("answer", f"{prov} (after discovery): {len(ans.get('matches') or [])} matches proposed")
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

        # 6. groundedness. With no matches there are no facts to check: say plainly that nothing verified was found
        #    (the checker would otherwise delete the honest "I couldn't find..." sentence and leave a misleading reply).
        if not matches:
            topic = ", ".join(_terms(plan, message)[:3]) or "that"
            if unverified:
                tail = " I found official gsu.edu pages below but couldn't verify them yet, so open them directly."
            else:
                tail = " Try naming a specific program, office or department, or ask your advisor."
            tr.add("note", "no verified match; answering honestly instead of guessing")
            return {"answer": f"I don't have verified GSU information about {topic} yet.{tail}", "matches": [], "trace": tr.steps,
                    "roadmap_id": None, "verification": {"checker": "none (no facts stated)", "removed_sentences": []},
                    "unverified": unverified}
        cited = [m["resource"] for m in matches]
        v = verify_grounded(ans.get("answer_text") or "", cited)
        tr.add("verify", f"{v['checker']}: " + ("all sentences supported" if v["grounded"] else f"removed {len(v['unsupported'])} sentence(s)"))
        roadmap_id = None
        if matches and re.search(r"\b(roadmap|plan|steps|step by step|path|timeline|schedule)\b", message.lower()):
            from .planner import build_roadmap
            rm = build_roadmap(message, [m["resource"]["id"] for m in matches] + [r["id"] for r in rows[:5]], profile, con)
            if rm:
                roadmap_id = rm["id"]
                tr.add("roadmap", f"saved '{rm['title']}' with {len(rm['steps'])} steps to the Roadmap tab")
        return {"answer": v["answer"] or "Here are the verified GSU resources that fit.", "matches": matches, "trace": tr.steps, "roadmap_id": roadmap_id,
                "verification": {"checker": v["checker"], "removed_sentences": v["unsupported"]},
                "unverified": unverified if not matches else []}
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
