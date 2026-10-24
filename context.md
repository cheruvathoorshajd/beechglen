# Nexus911 build context (handoff file)

Read this at the start of every session. Update it at the end of every stage
(state, checklist, decisions, next step). `.kiro/steering/context-pointer.md`
tells Kiro to do this automatically.

## Sources of truth (in this order)

1. `README.md`: features, formulas, defaults, field names, endpoints, demo outcomes.
2. `.kiro/steering/*.md`: conventions plus "Recorded deviations" from the playbook
   (LangGraph `app/flow/`, `app/context.py`, helper modules).
3. `KIRO_PROMPTS.md`: the build playbook (steps 0 to 6, lane prompts, Appendix A to D
   prompt texts that must be copied verbatim).
4. This file: decisions taken while building and the current state.

## Terminal rules (environment limits, not code problems)

The terminal tool times out on slow commands and garbles long or multi-line ones.

- Close a stuck terminal and use a fresh one before continuing.
- Every command short and on one line. No heredocs, no multi-line scripts, at most two chained commands.
- Create and edit files only with the file tools, never through the shell.
- Slow commands (pip, npm, servers, precompute) run in the background with a log:
  `nohup .venv/bin/pip install -r backend/requirements.txt > .kiro/logs/pip.txt 2>&1 &`
  then poll with `tail -5 .kiro/logs/pip.txt`. Never wait on them inline.
- Long output (pytest, scripts) goes to `.kiro/logs/` and is read with the file tools:
  `.venv/bin/python -m pytest -q > .kiro/logs/pytest.txt 2>&1`
- Always call `.venv/bin/python` and `.venv/bin/pip`; ignore the conda (base) env.
- Never print `.env`. Skip docker commands.
- If a command fails twice, change approach or ask the user. Don't loop.

## Environment

- Repo root: `/Users/kaushikj/Desktop/beechglen` (branch `main`, remote `origin`). Commit locally after each stage; never push.
- Python 3.13.2 at `/opt/homebrew/bin/python3`; venv at `.venv/` (no 3.11 locally; the Dockerfile uses python:3.11-slim, so code must stay 3.11-compatible).
- Node 22.15.1, npm 10.9.2.
- `.env` holds only `ANTHROPIC_API_KEY` (set). Every other setting uses its default.
- Logs: `.kiro/logs/` (gitignored).

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Orchestration is LangGraph in `backend/app/flow/` (state.py, builder.py, runner.py, nodes/); no `pipeline/orchestrator.py`. `flow.runner` exposes `process_call`, `confirm_link`, `split_call`. | Recorded deviation in structure.md and tech.md. |
| D2 | Two compiled graphs: intake (extract, verify) runs outside the store lock because it may call Claude; commit (locate, link, weigh, prioritize, dispatch) runs under `AppContext.lock` so concurrent calls link deterministically. | Replay thread and API requests run concurrently; LLM latency must not block reads. |
| D3 | `app/context.py` `AppContext` owns GraphStore, AuditLog, EventBus, FlowRunner, assist services, replay and agent sessions. API resolves it via a FastAPI dependency (`request.app.state.ctx`). | structure.md. |
| D4 | Model defaults are the README values `claude-sonnet-5-5` and `claude-haiku-5-5`. | The tech.md claim that they are not real was wrong: Anthropic's launch pages list both API IDs. |
| D5 | Contracts keep `extra="forbid"` (strict tool schemas). `pipeline/extract.py` sanitizes raw tool output before validation: unknown keys dropped, invalid enum values reset to defaults, invalid or out-of-vocabulary claims dropped. | tech.md fail-open rule. |
| D6 | `link.py` enforces the README itself: mutable attributes are excluded from the entity score, candidates must be inside the time window, H3 `grid_disk` prefilter then exact haversine. | Review issue 5. |
| D7 | Incident location = the highest-confidence location among non-provisional calls (ties go to the earliest). | README leaves it open; deterministic. |
| D8 | Novelty and overrides compare the call with an incident snapshot taken before the call is written. The "seen" set includes provisional claims; entity matching and consensus exclude them. | tech.md snapshot rule; README consensus rule. |
| D9 | Call priority uses the call's own severity (README worked example uses 0.80 for a duplicate even when the incident is higher). | README worked example. |
| D10 | Recency "now" = the incident's latest `received_at` (simulated clock). Repeat caller = an earlier call in the same incident with the same `caller_hash`. | Deterministic replays. |
| D11 | Timeline entries use simulated time; audit entries use wall-clock UTC. | Audit must be real time. |
| D12 | Scenario JSON is authored directly from the 0.3 prompt (rules followed exactly). The extraction cache is precomputed with the real API, then checked by scenario tests; clearly wrong cache entries may be fixed by hand (playbook I2). | Playbook 0.3 and I2. |
| D13 | Frontend scaffolded by writing files (create-vite prompts interactively): React 18, react-leaflet 4, Leaflet 1.9, Tailwind 3, Zustand, react-router-dom 6, Vite. Smoke tests with vitest + testing-library (dev dependencies only). | tech.md stack; no interactive prompts. |

## Build state

Done before this session (commit `d9ec1a3`): contracts.py, config.py, audit.py,
graph/store.py, pipeline/locate.py, pipeline/link.py (gaps below), reference.py,
geo.py, text.py, ids.py, paths.py, data/ma/*.json, data/dispatch_rules.json,
requirements.txt, pytest.ini, four steering files, `.kiro/specs/core-pipeline/design.md`.

Missing at session start: everything else in README (extract, verify, weigh,
priority, dispatch, flow, context, views, prompts, API, WebSocket, replay,
scripts, scenarios, cache, frontend, Dockerfile, tests).

### Issues from the last review

| # | Issue | Status |
|---|---|---|
| R1 | `llm/client.py` `call_tool` has no body | open |
| R2 | flow/ and context.py referenced but missing; design.md cites a missing "Design corrections" section | open (stage 5, stage 11) |
| R3 | config.py model defaults 4.5 instead of README 5.5; wrong tech.md note | open |
| R4 | `extra="forbid"` on Extraction conflicts with fail-open parsing | open (sanitizer) |
| R5 | link.py: mutable attrs in entity score, no time window, no H3 prefilter | open |
| R6 | `.env.example` was gitignored and missing | fixed (stage 0) |
| R7 | README lost team names (Dennis, Kaushik, Arvind) from commit b36af56 | open |

## Stage checklist

- [x] Stage 0: fresh venv + deps, `.kiro/logs/` ignored, `.env.example`, context.md, steering pointer
- [ ] Stage 1: review fixes R1, R3, R4 (sanitizer), R5, R7 + tests for locate, link, client, sanitizer
- [ ] Stage 2: scenario data `data/scenarios/{mass_ave_robbery,pike_crash,washington_st}.json` (playbook 0.3)
- [ ] Stage 3: `pipeline/weigh.py`, `priority.py`, `dispatch.py` + tests (A-5..A-7)
- [ ] Stage 4: `llm/prompts.py` (Appendix A-D verbatim), `pipeline/extract.py`, `pipeline/verify.py` + tests (B-1..B-3)
- [ ] Stage 5: `flow/`, `context.py`, `graph/views.py`, store additions + flow test (A-8)
- [ ] Stage 6: `realtime/bus.py`, `api/routes_*.py`, `main.py`, `run.py`, `llm/assist.py` (ask-next, briefing), `sim/replay.py` + API tests (B-4..B-7)
- [ ] Stage 7: `scripts/precompute_extractions.py`, `scripts/evaluate.py`; run precompute (I2); `test_scenarios.py` (I4); evaluation table in README (P1)
- [ ] Stage 8: frontend (0.6, 0.7, C-1..C-7, I3, P2) + build + smoke tests + mock/contract check
- [ ] Stage 9: Dockerfile and .dockerignore (C-8). Deploy (P3) is left to the user.
- [ ] Stage 10: stretch S1 caller chat, S2 corroboration agent + panel + tests
- [ ] Stage 11: full test run, README layout/evaluation, specs tasks.md, design.md corrections, final context.md

## Verification log

(Append one line per stage: command, log file, result.)

- Stage 0: `import fastapi, h3, langgraph, anthropic, pytest` → `.kiro/logs/import-check.txt` = ok. Versions in `.kiro/logs/pip-list.txt`: fastapi 0.119.1, uvicorn 0.39.0, pydantic 2.14.1, pydantic-settings 2.16.1, networkx 3.7, h3 4.5.0, langgraph 0.6.11, anthropic 0.125.0, httpx 0.28.1, pytest 8.4.2.

## Next step

Stage 1: review fixes, starting with R3 (config.py model defaults and the tech.md note).
