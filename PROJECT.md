# Pathfinder: PROJECT.md (spec)

**One-liner.** An agentic resource hub that matches Perimeter College Clarkston students to verified GSU programs, people and
events, keeps that data fresh on its own, and alerts students when something new fits them.

**Who.** Perimeter College students at Clarkston: commuters with jobs, many first-gen and Pell-eligible, most aiming for the
downtown Atlanta campus. **Job:** "Show me the real GSU resources that fit my situation right now, who to contact, and what to do
first, without me having to know what to search for."

**Sponsor fit.** The demo path uses ENI (Entrepreneurship & Innovation Institute) programs; ENI is a HackPerimeter sponsor.

## Must have (demo flow) and where it lives
| Feature | File(s) |
|---|---|
| Demo profile (Jordan) from `demo_profile.json` | `backend/config/demo_profile.json`, `app/db.py` |
| SQLite KB: resources, sources, alerts, ingestion_runs, profile, FTS5 | `app/db.py` |
| Curated source allowlist | `backend/config/sources.yaml`, `app/ingest/fetch.py` |
| Ingestion agent: fetch → parse → LLM extract → evidence check → hash diff → upsert | `app/agents/ingestion.py`, `app/ingest/*` |
| Router agent: plan → FTS → stale refetch → answer → verify → trace | `app/agents/router.py`, `app/agents/verify.py` |
| Match cards (why / contact / first step / source / verified date) | `frontend/src/components/MatchCard.tsx` |
| Email draft | `POST /api/draft-email`, `EmailDraftModal.tsx`, `prompts/email.txt` |
| Trace panel | `TracePanel.tsx` |
| Watcher agent → alerts, bell + toast (5s polling) | `app/agents/watcher.py`, `AlertsBell.tsx`, `App.tsx` |
| Sources page with Run now / Run all | `SourcesPage.tsx`, `POST /api/sources/{id}/run`, `POST /api/ingest/run-all` |
| Roadmap page from `pathways.yaml` | `RoadmapPage.tsx`, `GET /api/pathways/{id}/roadmap` |
| `llm()` wrapper: Gemini primary, Groq failover | `app/llm.py` |
| APScheduler jobs (optional, `SCHEDULER_ENABLED=1`) | `app/scheduler.py` |
| Profile modal (optional) | `ProfileModal.tsx`, `PUT /api/profile` |

## Endpoints (prefix /api)
`GET /health` · `GET|PUT /profile` · `POST /chat` · `POST /draft-email` · `GET /resources?topic=&campus=&type=` · `GET /pathways` ·
`GET /pathways/{id}/roadmap` · `GET /sources` · `POST /sources/{id}/run` · `POST /ingest/run-all` · `GET /alerts?unread=1` · `POST /alerts/{id}/read`

## Data rules
Page text only; missing field = null; `evidence` must appear verbatim in the normalized page text or the row is dropped;
campus may be narrowed from the source default, never widened; contacts stay office-level unless the page names a person with a role.
No hand-written seed data. Watcher rule: status new/changed, topic overlap ≥ 1, not `atlanta_only` unless topics include `transition`,
events need `event_start >= now`.

## Fallbacks
Gemini fails → Groq. Both fail → `DEMO_FALLBACK=1` serves `data/demo_cache.json` for the two demo queries; otherwise top search hits
with a lexical groundedness check. GSU site down / Wi-Fi drops → stored rows, trace says "using copy from <date>".
ENI feed has nothing new → `scripts/demo_reset.py` before "Run now". App fails on stage → 2-minute backup video.

## Timeline
Hacking 10:30-5:30 · feature freeze 4:15 · hard stop 4:30 · submit by 5:30 (Discord form) · pitch 7:00 (90 seconds).
