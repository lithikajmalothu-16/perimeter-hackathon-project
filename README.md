# Pathfinder · Georgia State

> **Students can't ask about a resource they don't know exists.** Pathfinder finds it for them, proves it's real, and pings them when something new fits.

**[▶ Try it live](https://perimeter-hackathon-project.vercel.app)** · Built from **8 AM to 9 PM** in one day at **HackPerimeter 2026**
(GSU Perimeter College, Clarkston) by Lithika Jadav Malothu and Manjunath Ande.

---

## The problem

Georgia State's support for students is spread across dozens of department sites, calendars, and PDFs. A Perimeter College student
at Clarkston, often a commuter with a job and the first in their family at college, has no map of it. The Hope Center's 2023-24 survey
found **65% of students didn't know the support existed.**

A generic chatbot doesn't fix this, for two reasons:

1. It only answers the questions a student already knows to ask.
2. It invents GSU details: offices that moved, deadlines that passed, emails that never existed.

## What Pathfinder does differently

- **It flips the flow.** The student says what they're trying to do ("I want to turn my side hustle into a business"). Pathfinder brings
  back the programs, people, and events that fit: who to contact, what to do first, and a link to the page that proves it.
- **It can't make things up.** Every fact traces back to a quote copied **word for word** from an official gsu.edu page. No quote, no card.
- **It keeps itself current.** Agents re-read GSU's calendars and pages on a schedule, notice what changed, and alert the students it matters to.

## Highlights

- 🔒 **Verbatim evidence or it doesn't exist.** The LLM must return the exact sentence it extracted each fact from. Code (not the model)
  checks that sentence is on the page. If it isn't, the row is thrown away.
- ✂️ **A fact-checker after every answer.** Sentences the retrieved sources don't support are cut before the student sees them,
  and the answer says plainly when nothing verified matches.
- 🌐 **Finds pages nobody curated.** Ask about something new ("medicine") and Pathfinder searches gsu.edu live, verifies the pages on the
  spot, and shows them as **found live** cards.
- 🔔 **Alerts without asking.** A new ENI workshop goes up on the calendar → it lands as a toast and a bell notification for students whose interests match.
- 🗺️ **Chat → roadmap in one tap.** "Make this my roadmap" turns verified cards into dated steps (this week, within 2 weeks, this semester) the student can check off.
- 🔎 **Shows its work.** A trace panel lists every step the agents took: the plan, the search, the refetches, what the checker removed.
- 📍 **Campus-aware.** All 7 GSU campuses; results from the student's own campus rank first.
- ✉️ **One-tap outreach.** "Draft email" writes an editable intro email to the right office.
- 🎙️ **Voice input** with a live transcript.
- 🛟 **Doesn't fall over on stage.** Gemini → Groq failover, a lexical fallback checker if both LLMs are down, and stored copies when a GSU site is unreachable.

## The agents

Six agents, each with one job and one rule it can't break.

| Agent | What it does | The rule it enforces |
|---|---|---|
| **Ingestion** (`agents/ingestion.py`) | Fetches each source (RSS feeds, pages, calendars), parses it, has the LLM extract programs, events, contacts, deadlines and eligibility, then compares a content hash to label each row *new*, *changed* or *unchanged* before saving it. | It is the **only** code allowed to write to the knowledge base, and every row must carry a verbatim evidence quote and its source URL. |
| **Router** (`agents/router.py`) | Handles every chat message: turns the question into a JSON search plan, runs full-text search over the knowledge base, ranks results by campus, re-fetches any row older than the freshness window, then writes the answer and up to 3 match cards. | It throws out any card whose resource wasn't actually retrieved, so the LLM can't cite something it invented. |
| **Verifier** (`agents/verify.py`) | Reads the finished answer sentence by sentence against the retrieved rows and removes anything they don't support. | It only judges; it never rewrites. With no LLM reachable it falls back to a keyword-overlap check. |
| **Discovery** (`agents/discovery.py`) | When the knowledge base has nothing on a topic, searches Google (Gemini with Search grounding, Groq Compound as backup) for official gsu.edu pages, then sends each page through the ingestion agent. | The gsu.edu filter is enforced **in code**, not in a prompt. Pages that fail verification only appear as plain links in a "not verified yet" box, never as cards. Every URL it finds is queued for human approval. |
| **Watcher** (`agents/watcher.py`) | Runs after every ingestion run and turns new or changed rows into alerts. | It alerts only on rows that share a topic with the student's profile, are on a campus they can use, and (for events) haven't happened yet. |
| **Planner** (`agents/planner.py`) | Turns the cards from a conversation into an ordered, checkable roadmap. | Every step must cite a resource that was retrieved; the same rule as the router. |

A scheduler (APScheduler) drives ingestion on its own: calendars every 3 hours, pages every 24 hours. Every model call goes through one
wrapper, `llm.py`, which tries Gemini, fails over to Groq, strips `<think>` blocks, and validates the JSON.

## How the system is grounded

Grounding happens at five checkpoints, so a made-up fact has to get past all of them to reach a student:

```
 1. ALLOWLIST     fetch.py only requests gsu.edu and its subdomains, 1 request/second, with an identifiable user agent
        │
 2. EVIDENCE      the LLM extracts each resource with an exact quote; code checks that quote appears in the
        │         normalized page text, word for word, or the row is dropped
        │
 3. RETRIEVAL     the answer can only cite rows that search actually returned; any other card is removed
        │
 4. VERIFICATION  verify_grounded() deletes answer sentences the retrieved rows don't support
        │
 5. PROVENANCE    each card shows its source link and the date it was last verified; stale rows are re-fetched
                  before answering, and if a site is down the trace says "using copy from <date>"
```

There is **no hand-written seed data**: every row in the knowledge base was put there by the ingestion agent, with its quote and URL.

## Architecture

```
React (Vite) ──HTTP JSON──► FastAPI
                              ├─ Router ──► plan → SQLite FTS5 search → refetch stale rows → answer → Verifier
                              │                └─► Discovery (nothing found) → live gsu.edu search → Ingestion
                              ├─ Ingestion ──► allowlisted fetch → parse RSS/HTML → LLM extract → evidence check → hash diff → upsert
                              ├─ Watcher ──► new/changed rows matching a profile → alerts (bell + toast)
                              ├─ Planner ──► verified cards → dated, checkable roadmap
                              └─ APScheduler ──► Ingestion (calendars every 3h, pages every 24h)
                                         every LLM call ──► llm.py: Gemini, failover to Groq
```

## Stack

**Backend** Python 3.11 · FastAPI · SQLite + FTS5 · httpx · APScheduler · Gemini (with Google Search grounding) · Groq
**Frontend** React 18 · Vite · TypeScript · Tailwind
**Deploy** Vercel (frontend, `frontend/vercel.json`) · Render (API, `render.yaml`)

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

Text-message alerts, roadmaps for more majors beyond Business Administration, multilingual answers, and advisor booking.
