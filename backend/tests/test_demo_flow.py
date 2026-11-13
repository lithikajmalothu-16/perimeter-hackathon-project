"""End-to-end demo flow with no network and no API keys: fetch and the extraction LLM are faked with fixtures,
everything else (parsers, evidence check, hash diff, FTS search, router fallback, watcher, alerts, email) is real.
Run from backend/:  pytest -q"""
import importlib
import os
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "t.db"))
    monkeypatch.setenv("GEMINI_API_KEY", ""); monkeypatch.setenv("GROQ_API_KEY", "")
    from app import config
    importlib.reload(config)
    config.settings.database_path = tmp_path / "t.db"
    config.settings.gemini_api_key = config.settings.groq_api_key = ""
    from app import db, llm
    from app.ingest import fetch as fetch_mod, extract as ex
    from app.agents import ingestion

    def fake_fetch(url, timeout=20.0):
        if url.endswith("/calendar/xml"):
            return url, (FIX / "eni.xml").read_text(), 200
        if "advisement" in url:
            return url, (FIX / "advising.html").read_text(), 200
        raise fetch_mod.FetchError("http 404")
    monkeypatch.setattr(ingestion, "fetch", fake_fetch)

    def fake_llm(prompt, schema_hint="", system=""):
        if "rows" in schema_hint:
            return {"rows": [
                {"name": "Perimeter College Advisement Center", "type": "office", "campus": "clarkston", "topics": ["advising"],
                 "summary": "Assigned academic advisors for Perimeter students; removes advisement holds.",
                 "how_to_start": "Schedule an appointment through Navigate", "contact_office": "Perimeter College Advisement",
                 "contact_email": "pcadvisement@gsu.edu", "location_building": "Building CN", "location_room": "1100",
                 "evidence": "An advisement hold means you must meet with your advisor before you can register for classes."},
                {"name": "Invented Office", "type": "office", "evidence": "This sentence is not on the page."}]}, "fake"
        raise llm.LLMError("no llm in tests")
    monkeypatch.setattr(ex.llm, "complete_json", fake_llm)

    from fastapi.testclient import TestClient
    from app import main
    importlib.reload(main)
    with TestClient(main.app) as c:
        yield c


def test_demo_flow(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/profile").json()["name"] == "Jordan"                        # step 1

    r = client.post("/api/sources/eni_cal/run").json()                                     # ingestion + watcher
    assert r["run"]["rows_new"] == 2 and r["alerts_created"] >= 1
    again = client.post("/api/sources/eni_cal/run").json()
    assert again["run"]["rows_new"] == 0 and again["alerts_created"] == 0                  # hash diff: unchanged

    adv = client.post("/api/sources/perimeter_advising/run").json()["run"]
    assert adv["rows_new"] == 1 and adv["rows_dropped"] == 1                               # evidence check dropped the invented row

    chat = client.post("/api/chat", json={"message": "I want to turn my side hustle into a real business. Where do I start?"}).json()
    assert chat["matches"] and any("ntrepreneur" in m["resource"]["name"] or "Pitch" in m["resource"]["name"] for m in chat["matches"])
    assert [t["step"] for t in chat["trace"]][:2] == ["plan", "search"]                    # step 2 + trace

    hold = client.post("/api/chat", json={"message": "What does my advisement hold mean and who do I talk to?"}).json()
    assert hold["matches"][0]["resource"]["contact_email"] == "pcadvisement@gsu.edu"       # step 4

    email = client.post("/api/draft-email", json={"resource_id": hold["matches"][0]["resource"]["id"]}).json()
    assert email["to"] == "pcadvisement@gsu.edu" and "Jordan" in email["body"]             # step 3

    road = client.get("/api/pathways/business_admin/roadmap").json()                       # step 5
    assert len(road["steps"]) == 6 and road["steps"][0]["resources"]

    alerts = client.get("/api/alerts?unread=1").json()                                     # step 6
    assert alerts and alerts[0]["message"].startswith("New ENI event matches your interests")
    assert client.post(f"/api/alerts/{alerts[0]['id']}/read").json()["ok"]
    srcs = client.get("/api/sources").json()
    assert any(s["id"] == "eni_cal" and s["last_status"] in ("ok", "unchanged") for s in srcs)
