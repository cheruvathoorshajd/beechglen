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
| D14 | `llm/client.py` `model_profile()` picks request settings per model. Sonnet 5.5: `tool_choice auto` + `strict: true` + `thinking between_tools`, no temperature. Haiku 5.5: forced tool, no temperature. 4.x models: forced tool + temperature 0. All tools are sent `strict: true`; `llm/schema.tool_schema()` makes schemas strict-compatible (refs inlined, all properties required, `additionalProperties: false`, no min/max/default). | Anthropic Sonnet 5.5 and Haiku 5.5 migration guides: 5.x models reject temperature; Sonnet 5.5 rejects forced tool_choice; strict mode allows at most 24 optional params. |
| D16 | Dispatch: field names are `location`, `type`, `injuries`, `weapons`, `hazard`, `trapped`, then `<subject>.<attribute>` (frontend prettifies). `type` confidence = share of non-provisional calls reporting the incident type. Agencies: police (highway → State Police, landmark agency_hint, else town PD), plus fire/EMS by type, flags or units text. When the incident has no town, `agencies.json` `psap_towns` supplies the PSAP's town. Leads have stable keys (`plate:<v>`, `vehicle:<subject>`, `direction_of_travel:<subject>`, `suspect_location:<subject>`) so a suggested lead is updated, not duplicated. | README leaves these open; keeps routing total. |
| D17 | Overrides: `new_weapon` if a weapon value is unseen or the weapon flag is new; `new_injury` if the call reports any injury and the incident had none; `injury_increase` only when the incident already had a count; `new_hazard` per category (fire/smoke, trapped). A call that creates an incident gets only `new_incident` (no floor). | README "6. Prioritize". |
| D15 | Gazetteer fixes found while testing: phrase aliases match whole words after suffix expansion ("Massachusetts Avenue" used to become "massachusetts avenuenue"); suffix-less names ("Boylston") match "boylston street"; route aliases match whole words ("I-290" no longer maps to I-90); exit text like "exit 63" parses; landmark aliases match whole words and the raw location text is scanned only when no street or landmark was extracted ("ran toward Hynes" no longer relocates a store call to the station). | Each one broke a demo scenario path. |

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
| R1 | `llm/client.py` `call_tool` has no body | fixed (stage 1, D14) |
| R2 | flow/ and context.py referenced but missing; design.md cites a missing "Design corrections" section | open (stage 5, stage 11) |
| R3 | config.py model defaults 4.5 instead of README 5.5; wrong tech.md note | fixed (stage 1); tech.md now records the real 5.x API constraints |
| R4 | `extra="forbid"` on Extraction conflicts with fail-open parsing | fixed (stage 1): `llm/schema.sanitize()`; extract.py must call it (stage 4) |
| R5 | link.py: mutable attrs in entity score, no time window, no H3 prefilter | fixed (stage 1) |
| R6 | `.env.example` was gitignored and missing | fixed (stage 0) |
| R7 | README lost team names (Dennis, Kaushik, Arvind) from commit b36af56 | fixed (stage 1): header line only; lane owners stay `<A>/<B>/<C>` (mapping unknown) |

## Stage checklist

- [x] Stage 0: fresh venv + deps, `.kiro/logs/` ignored, `.env.example`, context.md, steering pointer
- [x] Stage 1: review fixes R1, R3, R4 (sanitizer), R5, R7 + tests for locate, link, client, sanitizer
- [x] Stage 2: scenario data `data/scenarios/{mass_ave_robbery,pike_crash,washington_st}.json` (playbook 0.3); rules locked by `test_scenario_data.py`
- [x] Stage 3: `pipeline/weigh.py`, `priority.py`, `dispatch.py` + tests (A-5..A-7)
- [x] Stage 4: `llm/prompts.py` (Appendix A-D verbatim), `pipeline/extract.py`, `pipeline/verify.py` + tests (B-1..B-3)
- [x] Stage 5: `flow/`, `context.py`, `graph/views.py`, store additions + flow test (A-8)
- [x] Stage 6: `realtime/bus.py`, `api/routes_*.py`, `main.py`, `run.py`, `llm/assist.py` (ask-next, briefing), `sim/replay.py` + API tests (B-4..B-7)
- [ ] Stage 7: `scripts/precompute_extractions.py`, `scripts/evaluate.py`; run precompute (I2); `test_scenarios.py` (I4); evaluation table in README (P1)
- [ ] Stage 8: frontend (0.6, 0.7, C-1..C-7, I3, P2) + build + smoke tests + mock/contract check
- [ ] Stage 9: Dockerfile and .dockerignore (C-8). Deploy (P3) is left to the user.
- [ ] Stage 10: stretch S1 caller chat, S2 corroboration agent + panel + tests
- [ ] Stage 11: full test run, README layout/evaluation, specs tasks.md, design.md corrections, final context.md

## Verification log

(Append one line per stage: command, log file, result.)

- Stage 0: `import fastapi, h3, langgraph, anthropic, pytest` → `.kiro/logs/import-check.txt` = ok. Versions in `.kiro/logs/pip-list.txt`: fastapi 0.119.1, uvicorn 0.39.0, pydantic 2.14.1, pydantic-settings 2.16.1, networkx 3.7, h3 4.5.0, langgraph 0.6.11, anthropic 0.125.0, httpx 0.28.1, pytest 8.4.2.

- Stage 1: `.venv/bin/python -m pytest > .kiro/logs/pytest-stage1.txt` → 60 passed (test_locate, test_link, test_llm_client, test_schema). Note: pytest.ini already passes `-q`; adding another `-q` hides the summary line.

- Stage 2: 0.3 one-liner → `.kiro/logs/scenarios-check.txt` = ok (28 calls parse as CallIn); `test_scenario_data.py` → `.kiro/logs/pytest-stage2.txt` = 6 passed.

- Stage 3: full suite → `.kiro/logs/pytest-stage3.txt` = 104 passed (adds test_weigh, test_priority, test_dispatch; README worked example 3/90/100 and 0.83/0.17 verified).

- Stage 4: full suite → `.kiro/logs/pytest-stage4.txt` = 131 passed (adds test_verify, test_extract, test_prompts; prompts match KIRO_PROMPTS.md verbatim).

- Stage 5: full suite → `.kiro/logs/pytest-stage5.txt` = 139 passed (adds test_flow: duplicates, new weapon, fire gate, split, ambiguous suggest + confirm, Pike exits/transfer/injury, fail-open extraction, reset).

- Stage 6: full suite → `.kiro/logs/pytest-stage6b.txt` = 150 passed, 0 warnings (adds test_api: every README endpoint in OpenAPI, WebSocket event, ask-next/briefing fallbacks, confirm/split 409/404, leads, settings validation, metrics, audit, replay + reset, SPA fallback). Live smoke: `nohup .venv/bin/python run.py > .kiro/logs/server.txt 2>&1 &` → `/openapi.json` 200, `/docs` 200, `/api/queue` 200 (`.kiro/logs/smoke.txt`); server stopped afterwards.

## Module interfaces built so far

- `pipeline.extract`: `Extractor(tool_caller=None, settings=get_settings, cache_dir=EXTRACTION_CACHE_DIR)`; `extractor(call) -> Extraction` (role hint applied), `.extract_raw(call)`, `.precompute(call) -> "cached"|"extracted"|"failed"`; module `extract(call)`. Cache file JSON = `{transcript, channel, model, extraction}`.
- `pipeline.verify.ground(extraction, transcript) -> list[ClaimStatus]`; whole-word exact match → verified, ≥0.80 token coverage → pending, else rejected.
- `pipeline.locate.resolve(mention, device, reference)`; `pipeline.link.decide(CallFeatures, [IncidentCandidate], settings) -> LinkOutcome`.
- `pipeline.weigh`: `ClaimEvidence`, `claim_weight`, `repeat_callers`, `consensus`, `contradictions`, `consensus_lookup`.
- `pipeline.priority`: `severity`, `IncidentSnapshot.build`, `novelty`, `override_reasons`, `priority`, `to_display`, `queue_order`.
- `pipeline.dispatch`: `CallFacts`, `ClaimRef`, `build_package`, `is_dispatch_ready`, `suggest_leads -> [LeadSuggestion(key, description, source_claim_ids)]`.
- `llm.client.call_tool(...)`, `llm.schema.tool_schema/sanitize`, `llm.prompts.*_SYSTEM/*_TOOL/MISSING_RULES/AGENT_*`.
- `context.AppContext.create(extract=..., ground=...)` → `.store`, `.audit`, `.lock` (RLock), `.runner`, `.views`; `.reset()` clears graph + audit, keeps runtime settings.
- `flow.runner.FlowRunner`: `process_call(CallIn) -> ProcessResult` (intake graph unlocked, commit graph under lock; naive times treated as UTC), `confirm_link(call_id)`, `split_call(call_id)`; both raise `LinkActionError` (→ 409) when not applicable.
- `flow.ops`: `refresh_header`, `reweigh`, `refresh_dispatch`, `recompute_incident`, `sim_now` (latest call time).
- `graph.views.GraphViews`: `queue()`, `incidents()`, `incident_detail(id)`, `call_detail(id)`, `explain(call_id)`, `metrics()`, `create_lead(...)` (status open, audited officer), `update_lead(...)`; raise `NotFoundError` (→ 404).
- Store: ids come from a per-store `IdGenerator` (`store.new_id(kind)`): `c-0001`, `inc-0001`, `clm-0001`, `lead-0001`; reset restarts them. Audit ids `aud-0001`.
- Audit actions: `link.decided` (system), `priority.override` (system), `link.confirmed` / `link.split` (operator), `lead.created` / `lead.updated` (officer).
- `AppContext` also owns `.bus` (EventBus), `.assist` (AssistService), `.replay` (ReplayController); `create(..., tool_caller=None, scenario_dir=SCENARIO_DIR)`. `reset()` stops the replay before taking the lock (its thread may hold/await the lock).
- `realtime.bus`: `EventBus.publish(type, payload)` thread-safe via `call_soon_threadsafe`; `/ws/dashboard` subscribes before accept; `call_processed_payload(result, **extra)` includes `override_reasons` (for NEW INFO toasts). `recent()` keeps the last 200 events (tests).
- `llm.assist.AssistService`: `ask_next(CallDetail, IncidentDetail)`, `briefing(IncidentDetail)`; cache keys include incident last_seen and timeline length; questions naming a contested value are dropped; template adds "Are you safe right now?" first for victims.
- `sim.replay`: `load_scenario(id)`, `ReplayController.start(id, speed)/stop()/reset()/status()/sim_time()/join()`; scenario ids must match `^[a-z0-9_]{1,64}$` (no path traversal).
- `main.create_app(context_factory=None, frontend_dist=FRONTEND_DIST_DIR)`; module `app = create_app()`. Errors: NotFoundError/ScenarioNotFound → 404, LinkActionError → 409, settings validation → 422.
- Events published: `call.processed` (API + replay), `link.changed` (confirm/split), `lead.updated`, `settings.updated`, `sim.status` (start, every call, stop, end, reset), `incident.updated` `{reset: true}` on reset.

## Scenario data notes

- 28 calls: robbery c01-c12 (A, plus B = c12), pike p01-p12 (C), washington w01-w04 (D, E). Every robbery caller except c10 and c12 names Mass Ave and Boylston; flight directions are separate sentences ("He ran toward Hynes station"). Pike SUV is always mentioned before the pickup, so extraction maps the SUV to subject `vehicle`. Device jitter stays within ±0.0003.

## Test conventions

- `backend/tests/conftest.py` forces `DEMO_MODE=offline` and a blank `ANTHROPIC_API_KEY` before any app import, and resets settings and runtime thresholds around every test. No test touches the network.

## Next step

Stage 7: `scripts/precompute_extractions.py` (fills `data/cache/extractions/` for every scenario call via `Extractor.precompute`, skipping cached ones; needs the API key) and `scripts/evaluate.py` (replays every scenario in-process, cache only, prints the README metrics as a markdown table). Run precompute in the background with a log (real Claude calls, 28 transcripts). Then `test_scenarios.py` (I4 assertions, offline) and paste the evaluate table into README "Evaluation" (P1).
