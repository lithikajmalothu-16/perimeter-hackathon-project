# Pathfinder · Georgia State

> **Students can't ask about a resource they don't know exists.** Pathfinder finds it for them, proves it's real, and pings them when something new fits.

Built in one day at **HackPerimeter 2026** (GSU Perimeter College, Clarkston) by Lithika Jadav Malothu and Manjunath Ande.

---

## The problem

Georgia State's support for students is spread across dozens of department sites, calendars, and PDFs. A Perimeter College student
at Clarkston, often a commuter with a job and the first in their family at college, has no map of it. The Hope Center's 2023-24 survey
found **65% of students didn't know the support existed.**

A generic chatbot doesn't fix this, for two reasons:

1. It only answers the questions a student already knows to ask.
2. It invents GSU details: offices that moved, deadlines that passed, emails that never existed.

## What Pathfinder does differently

**It flips the flow.** The student says what they're trying to do ("I want to turn my side hustle into a business"). Pathfinder brings
back the GSU programs, people, and events that fit: who to contact, what to do first, and a link to the page that proves it.

**It won't make things up.** Every fact on a card is tied to a quote that has to appear **word for word** on an official gsu.edu page.
If the quote isn't on the page, the row is dropped. After the answer is written, a separate check removes any sentence the sources
don't back up.

**It keeps its own data fresh.** Agents re-read GSU calendars every few hours and pages every day, diff what changed, and alert
students when something new matches their interests.

## A tour in six questions

| The student… | Pathfinder… |
|---|---|
| Signs up with a GSU email, campus, and major | Ranks results from their own campus first (all 7 GSU campuses supported) |
| Asks *"I want to turn my side hustle into a real business. Where do I start?"* | Returns up to 3 cited match cards (ENI, LaunchGSU…) and shows its reasoning in a trace panel |
| Taps **Draft email** on a card | Writes an editable intro email to the right office |
| Asks *"What does my advisement hold mean?"* | Gives a cited advising answer, or says plainly that it found nothing verified |
| Asks about something the curated sources don't cover (*"medicine"*) | Searches gsu.edu live, runs each page through the same evidence check, and marks the cards **found live** |
| Taps **Make this my roadmap** | Turns verified cards into an ordered, checkable plan |

## How it works

```
React (Vite) ──HTTP JSON──► FastAPI
                              ├─ Router agent ──► plan → SQLite FTS5 search → refetch stale rows → answer → verify_grounded()
                              ├─ Ingestion agent ──► gsu.edu only → parse RSS/HTML → LLM extract → evidence check → diff → upsert
                              ├─ Discovery agent ──► live gsu.edu search when the KB has nothing → same ingestion pipeline
                              ├─ Watcher agent ──► new/changed rows matching a profile → alerts (bell + toast)
                              └─ APScheduler ──► calendars every 3h, pages every 24h
                                         every LLM call ──► llm(): Gemini, failover to Groq
```

Five agents, one rule each:

- **Ingestion** is the *only* thing allowed to write resources. No hand-written seed data: every row carries its source URL and evidence quote.
- **Router** plans the search, ranks campus-first, refetches anything stale, and drops any match it didn't actually retrieve.
- **Verifier** (`verify_grounded()`) cuts unsupported sentences. If no LLM is reachable it falls back to a lexical check.
- **Discovery** keeps URLs to gsu.edu in code, not in a prompt. Pages it can't verify only show up as plain links, never as cards.
- **Watcher** runs after every ingestion and turns relevant changes into alerts.

### Designed to survive a live demo

- Gemini down → Groq takes over. Both down → cached answers for the demo queries.
- A GSU site blocks bots or the Wi-Fi drops → answers come from the stored copy, and the trace says so with the date.
- Crawling is polite: an allowlist of gsu.edu URLs, 1 request/second, an identifiable user agent.

## Stack

**Backend** Python 3.11 · FastAPI · SQLite + FTS5 · httpx · APScheduler · Gemini (with Google Search grounding) · Groq
**Frontend** React 18 · Vite · TypeScript · Tailwind
**Deploy** Render (API, `render.yaml`) · Vercel (SPA, `frontend/vercel.json`)

## Run it locally

Needs Python 3.11+ and Node 20+.

```bash
cp .env.example .env              # add GEMINI_API_KEY (and GROQ_API_KEY for failover)

cd backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/init_db.py
python scripts/run_ingest.py      # crawls every enabled source in config/sources.yaml
uvicorn app.main:app --reload --port 8000

# second terminal
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Tests need no network and no keys: `cd backend && pytest -q`

<details>
<summary>Demo prep checklist</summary>

1. Set `STALE_HOURS=1` so the first query shows a live refetch.
2. `python scripts/smoke_demo.py` writes `data/demo_cache.json` (served when `DEMO_FALLBACK=1` and both LLMs fail).
3. `python scripts/demo_reset.py`, then **Run now** on `eni_cal` in the Sources tab to show new rows → alert toast → bell count.

</details>

## Repo map

```
backend/
  app/agents/     router, ingestion, discovery, watcher, planner, verify
  app/ingest/     fetch (allowlist + rate limit), RSS/HTML parsers, LLM extraction
  app/prompts/    every prompt as a plain text file
  config/         sources.yaml (allowlist), majors.yaml, pathways.yaml (roadmaps as data, not code)
  data/           seed_snapshot.db, the KB snapshot used for deploys
  tests/          offline tests with HTML/RSS fixtures
frontend/src/     Chat, Onboard, Roadmap, Sources pages + match cards, trace panel, alerts
docs/SPEC.md      the full build spec: features, endpoints, data rules, fallbacks
```

## Privacy

Pathfinder never asks about or stores income, immigration status, grades, or health. Sign-up accepts only `@student.gsu.edu` and
`@gsu.edu` emails. API keys stay in `.env`, which is gitignored.

## What's next

Text-message alerts, more major roadmaps beyond Business Administration, multilingual answers, and advisor booking.
