# Pathfinder · Georgia State

An agentic resource hub that matches Perimeter College Clarkston students to **verified** GSU programs, people and events,
keeps that data fresh on its own, and alerts students when something new fits them.

**Problem.** GSU information is spread across dozens of sites. Students don't know what exists, so they never ask
(Hope Center 2023-24: 65% of students were unaware of available support). Generic chatbots only answer questions students
already know to ask, and they hallucinate GSU details. Pathfinder reverses the flow: it finds the resources first and cites them.

## How it works
```
React (Vite) --HTTP JSON--> FastAPI
                             |-- router agent --> llm() --> Gemini | Groq (failover)
                             |       |--> KB search (SQLite FTS5)
                             |       |--> ingestion.refresh_source() on stale rows
                             |       '--> verify_grounded() --> llm()
                             |-- ingestion agent --> httpx (allowlisted gsu.edu URLs) --> parsers --> llm() extract --> SQLite
                             |-- watcher agent (runs after every ingestion run) --> SQLite alerts
                             '-- APScheduler (optional) --> ingestion agent (calendars 3h, pages 24h)
```
- **Ingestion agent** (the only writer to `resources`): fetch → parse (RSS / HTML) → Gemini extraction → **evidence check**
  (the quote must appear word for word on the page, else the row is dropped) → content-hash diff (new / changed / unchanged) → upsert.
- **Router agent**: JSON plan → FTS5 search (Clarkston > Perimeter/online > GSU-wide > Atlanta-only) → live refetch of stale rows →
  JSON answer → drops matches not in the retrieved set → `verify_grounded()` removes unsupported sentences → answer + trace.
- **Discovery agent**: when the curated KB has nothing on what the student asked (e.g. "medicine"), Gemini searches Google
  for official gsu.edu pages, the URLs are filtered to gsu.edu in code, and each page goes through the same ingestion pipeline
  and evidence check before it can appear as a card (badge: "found live"). New URLs are queued in `pending_sources`.
- **Watcher agent**: after every run, new/changed rows that overlap the profile's topics become alerts (bell + toast).
- **`llm()`**: Gemini primary, Groq failover, strips `<think>` blocks, validates JSON, one retry per provider.

## Run it (Windows PowerShell shown; macOS/Linux the same with `/` paths)
Needs Python 3.11+ and Node 20+.
```
copy .env.example .env          # add GEMINI_API_KEY (and GROQ_API_KEY for failover)

cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/run_ingest.py    # pulls every source in config/sources.yaml (needs internet)
uvicorn app.main:app --reload --port 8000

# second terminal
cd frontend
npm install
npm run dev                     # http://localhost:5173
```
Tests (no network, no keys): `cd backend && pytest -q`.

## Demo flow
0. Sign up: name, GSU email (@student.gsu.edu or @gsu.edu), campus, major. Or tap
   "Skip: use the demo student (Jordan)" (Business Administration at Clarkston, 30 credits, advisement hold).
1. Chat page with the student's profile chip, bell at 0.
2. "I want to turn my side hustle into a real business. I'm at Perimeter. Where do I start?" → answer + up to 3 cited match cards + trace.
3. "Draft email" on a card → editable intro email (or the contact page when no email is listed).
4. "What does my advisement hold mean and who do I talk to?" → cited advising answer.
4b. "I'm interested in medicine. What can I do at GSU right now?" → no curated rows → trace shows `discover` → "found live" cards from gsu.edu.
5. Roadmap tab → Business Administration → Robinson checklist, each step linked to its source.
6. Sources tab → `python scripts/demo_reset.py` beforehand → "Run now" on `eni_cal` → new rows, alert toast, bell count goes up.

Before the pitch: set `STALE_HOURS=1` so step 2 shows a live refetch, run `python scripts/smoke_demo.py` to write
`data/demo_cache.json` (served if both LLMs fail when `DEMO_FALLBACK=1`), then `python scripts/demo_reset.py`.

## Data sources
Only the URLs in `backend/config/sources.yaml` (gsu.edu and subdomains, 1 request/second, polite user agent):
ENI and LaunchGSU calendar feeds, the Perimeter viewbook, Perimeter advisement, and calendar.gsu.edu department/group pages.
Sources that hit a Cloudflare/AWS WAF challenge show `error` on the Sources page and answers fall back to the stored copy.
JSON APIs (Localist) are out of scope for now (`gsu_events_api` is listed but disabled).
**No hand-written seed data**: every row comes from an ingestion run (`origin: agent`) and carries its evidence quote and source URL.

## Out of scope
Phone messaging, Google Maps grounding, IBM Granite Guardian (separate branch), advising packet, multilingual,
parking, MARTA, advisor booking / Navigate scraping, user accounts, pathways beyond Business Administration, embeddings, WebSockets.

## Team
Lithika Jadav Malothu and Manjunath Ande · HackPerimeter 2026, GSU Perimeter College, Clarkston.
