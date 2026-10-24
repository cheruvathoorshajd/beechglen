---
inclusion: always
---

# Tech stack and conventions

## Backend
- Python 3.11, FastAPI, Pydantic v2, pydantic-settings, uvicorn, networkx, h3 v4 (latlng_to_cell, grid_disk, cell_to_latlng), langgraph, anthropic SDK, pytest, httpx.
- The package is `app` under backend/. run.py uses uvicorn with app_dir="backend"; pytest.ini sets pythonpath = backend; scripts insert backend/ into sys.path.
- Models live only in backend/app/contracts.py; settings only in backend/app/config.py.
- Locate, link, weigh, priority and dispatch are pure deterministic functions with no LLM calls.
- One in-memory GraphStore (networkx.MultiDiGraph) behind a repository class. No database.
- One EventBus; WebSocket /ws/dashboard sends DashboardEvent JSON. Only the API layer publishes events.
- Tests: pytest, deterministic, no network; mock the LLM client.

## Pipeline orchestration (LangGraph)
- The seven README pipeline stages run as LangGraph nodes in backend/app/flow/: extract, verify, locate, link, weigh, prioritize, dispatch.
- app/flow/ is the orchestration layer. app/graph/ is the knowledge graph. Never use one name for the other.
- State is a TypedDict (CallFlowState) in app/flow/state.py. Nodes return partial state dicts and never mutate their input.
- Nodes are built by factory functions that take an explicit dependency object, so no node reads a module-level global. Tests build a flow with fakes.
- Node modules hold no formulas. Every number comes from app/pipeline/*, which stays pure and independently testable.
- The link node snapshots the incident before writing to the store, because novelty must compare the call against the incident as it was beforehand.

## LLM (Claude)
- anthropic SDK. Models from env: CLAUDE_MODEL_EXTRACT, CLAUDE_MODEL_FAST. temperature 0.
- Structured output only by forcing one tool (tool_choice set to that tool) and validating the tool input with Pydantic. Never parse free text.
- Every LLM call has a 20-second timeout, one retry and a deterministic fallback. Failures never raise to the API caller.
- Extraction cache: data/cache/extractions/<sha256 of transcript>.json. DEMO_MODE is cache_first or offline.
- Prompt texts are in KIRO_PROMPTS.md Appendix A-D. Copy them verbatim into backend/app/llm/prompts.py.
- Extraction parsing is fail-open: unknown keys and out-of-vocabulary claims are dropped, never fatal.

## Frontend
- React + TypeScript (strict) from the Vite react-ts template, Tailwind CSS v3, Leaflet + react-leaflet, Zustand, react-router-dom. No other UI, chart or component libraries.
- frontend/src/api/types.ts mirrors backend/app/contracts.py field for field.
- Dark dispatch-console theme. Priority colors: red at 80+, amber 50-79, slate below 50.

## Commands
- Backend: `python run.py` (port 8080, docs at /docs). Tests: `pytest -q` from the repo root.
- Frontend: `npm run dev` in frontend/ (port 5173; Vite proxies /api and /ws to 8080).
- Production: one container; FastAPI serves frontend/dist at / with SPA fallback; Cloud Run with --max-instances 1.

## Recorded deviations from KIRO_PROMPTS.md
- Local interpreter is Python 3.13, not 3.11. No code depends on the difference.
- CLAUDE_MODEL_EXTRACT defaults to claude-sonnet-4-5 and CLAUDE_MODEL_FAST to claude-haiku-4-5. The ids in KIRO_PROMPTS.md (claude-sonnet-5-5, claude-haiku-5-5) are not real Anthropic model ids.
- requirements.txt adds langgraph (orchestration), websockets (uvicorn WebSocket support) and pytest-asyncio.
- Lane A gains helper modules paths.py, ids.py, geo.py, text.py and reference.py. They hold no models and no settings.
