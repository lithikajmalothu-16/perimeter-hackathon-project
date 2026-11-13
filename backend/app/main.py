"""FastAPI app: routes (PRD 10), CORS, scheduler start."""
from __future__ import annotations
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import auth, db, llm, scheduler
from .agents import ingestion, router
from .config import CONFIG_DIR, load_demo_profile, load_pathways, prompt, settings
from .models import ChatRequest, DraftEmail, DraftEmailRequest, Onboard, Profile, SendCode, VerifyCode
import yaml

CAMPUS_VALUE = {"Clarkston": "clarkston", "Alpharetta": "perimeter_all", "Decatur": "perimeter_all", "Dunwoody": "perimeter_all",
                "Newton": "perimeter_all", "Online": "online", "Atlanta": "atlanta_only"}


def load_majors() -> list[dict]:
    return yaml.safe_load((CONFIG_DIR / "majors.yaml").read_text(encoding="utf-8"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if settings.scheduler_enabled:
        scheduler.start()
    yield
    scheduler.stop()


app = FastAPI(title="Pathfinder API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    try:
        con = db.connect(); con.execute("SELECT 1"); stats = db.kb_stats(con); con.close(); ok = True
    except Exception:
        ok, stats = False, {}
    return {"status": "ok", "db": ok, "llm_primary": "gemini" if settings.gemini_api_key else ("groq" if settings.groq_api_key else "none"),
            "llm_failover": "groq" if settings.groq_api_key else "none", "scheduler": settings.scheduler_enabled, "kb": stats}


@app.get("/api/profile")
def get_profile():
    return db.get_profile()


@app.put("/api/profile")
def put_profile(p: Profile):
    return db.save_profile(p.model_dump())


@app.get("/api/majors")
def majors():
    return load_majors()


@app.post("/api/auth/send-code")
def send_code(req: SendCode):
    r = auth.send_code(req.email)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return r


@app.post("/api/auth/verify")
def verify_code(req: VerifyCode):
    r = auth.check_code(req.email, req.code)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return r


@app.post("/api/onboard")
def onboard(req: Onboard):
    """Page 1 sign-up: verified GSU email + campus + major -> the profile every agent uses."""
    if not auth.token_ok(req.email, req.token):
        raise HTTPException(400, "Verify your GSU email first. Tap Send code.")
    if req.campus_name not in CAMPUS_VALUE:
        raise HTTPException(400, "Pick your GSU campus.")
    m = next((x for x in load_majors() if x["id"] == req.major), None)
    if not m:
        raise HTTPException(400, "Pick your major from the list.")
    topics = list(dict.fromkeys([*m["topics"], *[t.lower() for t in req.topics][:6]]))
    return db.save_profile({"name": req.name.strip(), "email": auth.norm(req.email), "email_verified": True, "campus": CAMPUS_VALUE[req.campus_name],
                            "campus_name": req.campus_name, "major": m["name"], "pathway_id": m.get("pathway_id"), "credits": 0, "work_hours": 0,
                            "holds": [], "interests": "", "topics": topics})


@app.post("/api/profile/demo")
def demo_profile():
    """Skip sign-up on stage: load the PRD demo student (Jordan)."""
    p = load_demo_profile()
    p.update({"email": "jordan.demo@student.gsu.edu", "email_verified": True, "major": "Business Administration (pathway)", "campus_name": "Clarkston"})
    return db.save_profile(p)


@app.post("/api/chat")
def chat(req: ChatRequest):
    return router.handle(req.message.strip(), [t.model_dump() for t in req.history], db.get_profile())


@app.post("/api/draft-email", response_model=DraftEmail)
def draft_email(req: DraftEmailRequest):
    con = db.connect()
    r = db.get_resource(con, req.resource_id)
    con.close()
    if not r:
        raise HTTPException(404, "unknown resource")
    p = db.get_profile()
    first = (p.get("name") or "Student").split()[0]
    office = r.get("contact_office") or r["name"]
    try:
        out, _ = llm.complete_json(
            prompt("email").replace("{profile}", json.dumps(p)).replace("{resource}", json.dumps({k: r.get(k) for k in
                ["name", "type", "summary", "how_to_start", "contact_office", "contact_email", "event_start", "location_building"]})),
            schema_hint='{"subject": str, "body": str}')
        subject, body = out.get("subject") or f"Question from a Perimeter student about {r['name']}", out.get("body") or ""
    except llm.LLMError:
        subject = f"Question from a Perimeter student about {r['name']}"
        body = (f"Hello {office} team,\n\nMy name is {first}. I'm a Perimeter College student at the "
                f"{(p.get('campus') or 'Clarkston').title()} campus with {p.get('credits', 0)} credits, planning to move to the Atlanta campus. "
                f"{p.get('interests') or ''}\n\nI'd love to learn how to get started with {r['name']}. "
                f"Could you tell me the best first step, or a good time to come by?\n\nThank you,\n{first}")
    return {"to": r.get("contact_email"), "subject": subject, "body": body, "contact_url": r.get("source_url")}


@app.get("/api/resources")
def resources(topic: str | None = None, campus: str | None = None, type: str | None = Query(None)):
    con = db.connect()
    out = db.list_resources(con, topic, campus, type)
    con.close()
    return out


@app.get("/api/pathways")
def pathways():
    return [{k: p[k] for k in ("id", "name", "start", "destination")} for p in load_pathways()]


@app.get("/api/pathways/{pid}/roadmap")
def roadmap(pid: str):
    p = next((x for x in load_pathways() if x["id"] == pid), None)
    if not p:
        raise HTTPException(404, "unknown pathway")
    con = db.connect()
    steps = []
    for st in p["steps"]:
        src = db.get_source(con, st["source_id"]) or {}
        steps.append({"title": st["title"], "source_id": st["source_id"], "source_url": src.get("url"), "source_label": src.get("label"),
                      "resources": db.rows_for_source(con, st["source_id"], 3)})
    con.close()
    return {"pathway": {k: p[k] for k in ("id", "name", "start", "destination", "topics")}, "steps": steps}


@app.get("/api/sources")
def sources():
    con = db.connect()
    out = db.list_sources(con)
    con.close()
    return out


@app.post("/api/sources/{sid}/run")
def run_source(sid: str):
    con = db.connect()
    if not db.get_source(con, sid):
        con.close()
        raise HTTPException(404, "unknown source")
    run = ingestion.run_source(sid, con)
    con.close()
    return {"run": run, "alerts_created": run.get("alerts_created", 0)}


@app.post("/api/ingest/run-all")
def run_all():
    runs = ingestion.run_all()
    return {"runs": runs, "alerts_created": sum(r.get("alerts_created", 0) for r in runs)}


@app.get("/api/alerts")
def alerts(unread: int = 0):
    con = db.connect()
    sql = ("SELECT a.*, r.name AS resource_name, r.source_url, r.event_start FROM alerts a LEFT JOIN resources r ON r.id=a.resource_id "
           + ("WHERE a.read=0 " if unread else "") + "ORDER BY a.id DESC LIMIT 50")
    out = [dict(x) for x in con.execute(sql).fetchall()]
    con.close()
    return out


@app.post("/api/alerts/{aid}/read")
def read_alert(aid: int):
    con = db.connect()
    con.execute("UPDATE alerts SET read=1 WHERE id=?", (aid,))
    con.commit(); con.close()
    return {"ok": True}
