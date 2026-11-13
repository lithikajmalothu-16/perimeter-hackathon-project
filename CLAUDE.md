# CLAUDE.md: working on Pathfinder

- Spec: `PROJECT.md`. Do not add features outside it; check "Out of scope" first.
- Backend: Python 3.11+, FastAPI in `backend/app`. Run from `backend/`. Tests: `pytest -q` (no network, no keys; fixtures in `tests/fixtures`).
- Frontend: React 18 + Vite 5 + TypeScript + Tailwind 3 in `frontend/`. Keep the artifact look: cream `#EAE5DE`/`#F4F0EA`,
  burnt orange `#C8642A`, ink `#1C2426`, sticky `#F7F3B5`, Archivo (wide, 900) + Work Sans, 2.5px ink borders, hard offset shadows
  (`shadow-hard`), tilted stickers, dashed connectors. No mascots.
- Rules that must not break:
  - `ingestion.py` is the only writer to `resources`. Every row needs `evidence` found verbatim in the normalized page text.
  - Agents fetch only URLs from `config/sources.yaml` (allow_domains gsu.edu + subdomains), 1 req/sec.
  - Every LLM call goes through `llm.complete_json()` (Gemini → Groq, `<think>` stripped, JSON validated).
  - Router drops matches whose `resource_id` wasn't retrieved, then runs `verify_grounded()`.
  - New pathway = YAML in `config/pathways.yaml`, never code.
  - Never ask about or store income, immigration status, grades or health.
- Secrets live in `.env` (gitignored). Never commit keys.
