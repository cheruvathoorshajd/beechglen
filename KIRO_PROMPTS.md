# Nexus911 — Kiro build playbook

Three teammates · 6,000 Kiro credits (2,000 per device) · 5 hours · `README.md` is the source of truth.

Every step lists **who** runs it, **where** (Manual, Claude chat, Kiro Vibe, Kiro Spec), the **prompt**, and **done when**. Credit numbers are estimates; Kiro charges by request complexity.

---

## Credit rules

1. Commit `README.md` and this file before the first Kiro prompt. Kiro reads them from the workspace, so prompts stay short.
2. Write the steering files by hand (Step 0.2). They cost nothing and load into every Kiro request.
3. Use the **Auto** model. Switch to a premium model only if a scoring task fails twice.
4. One spec per lane, three in total. If your Kiro version offers **Quick Spec** or a **Design-First** workflow, use it, because README.md already holds the design. Approve generated documents unless they contradict README.md; every refinement costs credits.
5. Run tasks with the **Start task** button in `tasks.md`, one at a time, and commit after each.
6. No agent hooks and no MCP servers.
7. Fix typos and one-line bugs by hand. For anything bigger, use the fix template at the end of this file.
8. Generate scenario data in Claude chat, not Kiro.

## Budget

| Device | Planned | Hard cap | Untouched reserve |
|---|---|---|---|
| A — core-pipeline | ~1,100 | 1,600 | 400 |
| B — api-llm-realtime | ~1,200 | 1,600 | 400 |
| C — console-ui | ~1,400 | 1,600 | 400 |
| **Total** | **~3,700** | **4,800** | **1,200** |

**Calibration gate:** when your first spec task finishes, open the usage dashboard. If that one task cost more than about 150 credits, drop both stretch steps immediately.

**Cut order if credits or time run short:** S2 agent → S1 caller chat → P2 polish → threshold sliders → leads board.

## Timeline

| Time | A (graph and scoring) | B (LLM, API, realtime) | C (console and demo) |
|---|---|---|---|
| 0:00–0:20 | 0.2 steering, 0.4 contracts | 0.3 scenarios, 0.5 stubs | 0.1 repo, 0.6 scaffold, 0.7 types and mocks |
| 0:20–0:35 | A1 spec | B1 spec | C1 spec |
| 0:35–2:30 | Tasks A-1 to A-8 | Tasks B-1 to B-8 | Tasks C-1 to C-8 |
| 2:30–3:15 | I4 scenario tests | I1 wire API, I2 precompute | I3 live data |
| 3:15–4:00 | P4 README results | P1 evaluate | P2 polish, P3 deploy |
| 4:00–4:30 | Debug support | S2 agent (stretch) | S1 caller chat (stretch) |
| 4:30–5:00 | Freeze: rehearse, record a backup video, final push | | |

Git rhythm after every task:

```bash
git add -A && git commit -m "<lane>-<task>" && git pull --rebase && git push
```

Lanes own separate folders (see `structure.md`), so conflicts should be rare.

---

## Step 0 — Setup (0:00–0:20)

### 0.1 Repo skeleton — C · Manual · 0 credits

```bash
mkdir nexus911 && cd nexus911 && git init -b main
mkdir -p .kiro/steering backend/app backend/tests data/ma data/scenarios data/cache/extractions scripts
# copy README.md and KIRO_PROMPTS.md into this folder
cat > .env.example <<'EOF'
ANTHROPIC_API_KEY=
DEMO_MODE=cache_first
CLAUDE_MODEL_EXTRACT=claude-sonnet-5-5
CLAUDE_MODEL_FAST=claude-haiku-5-5
PORT=8080
CORS_ORIGINS=http://localhost:5173
EOF
printf ".venv/\n.env\nnode_modules/\nfrontend/dist/\n__pycache__/\n.pytest_cache/\n" > .gitignore
git add -A && git commit -m "Nexus911 skeleton"
git remote add origin <repo-url> && git push -u origin main
```

`data/cache/` is committed on purpose so the demo is deterministic.

**Done when:** teammates can clone the repo and see README.md and KIRO_PROMPTS.md.

### 0.2 Steering files — A · Manual · 0 credits

Create these four files with exactly this content, then commit and push.

**`.kiro/steering/product.md`**

```markdown
---
inclusion: always
---

# Product: Nexus911

Nexus911 is a 5-hour hackathon prototype: a claim-weighted knowledge graph for 911 that links duplicate calls into incidents, weighs conflicting witness accounts, and prioritizes calls by new information, with a Massachusetts focus.

Users: 911 call-takers (operator console), supervisors (queue and metrics), police officers (briefing, dispatch package, leads).

Non-negotiable principles:
- No call is ever dropped or hidden. The system only reorders and annotates the queue.
- AI suggests, humans decide. Operators can confirm or split any link, and every decision is written to the audit log.
- Fail-open. LLM or network failures never block a call from entering the graph.
- Minority accounts stay visible: always return every value with its share.
- Caller-role credibility changes claim weight only, never call priority.
- Synthetic data only. No real 911 data or phone numbers.

README.md at the repo root is the source of truth for features, formulas, defaults, field names, endpoints and demo outcomes. Follow it exactly. Do not invent endpoints, fields, parameters or features that are not in README.md.
```

**`.kiro/steering/tech.md`**

```markdown
---
inclusion: always
---

# Tech stack and conventions

## Backend
- Python 3.11, FastAPI, Pydantic v2, pydantic-settings, uvicorn, networkx, h3 v4 (latlng_to_cell, grid_disk, cell_to_latlng), anthropic SDK, pytest, httpx.
- The package is `app` under backend/. run.py uses uvicorn with app_dir="backend"; pytest.ini sets pythonpath = backend; scripts insert backend/ into sys.path.
- Models live only in backend/app/contracts.py; settings only in backend/app/config.py.
- Locate, link, weigh, priority and dispatch are pure deterministic functions with no LLM calls.
- One in-memory GraphStore (networkx.MultiDiGraph) behind a repository class. No database.
- One EventBus; WebSocket /ws/dashboard sends DashboardEvent JSON. Only the API layer publishes events.
- Tests: pytest, deterministic, no network; mock the LLM client.

## LLM (Claude)
- anthropic SDK. Models from env: CLAUDE_MODEL_EXTRACT (default claude-sonnet-5-5), CLAUDE_MODEL_FAST (default claude-haiku-5-5). temperature 0.
- Structured output only by forcing one tool (tool_choice set to that tool) and validating the tool input with Pydantic. Never parse free text.
- Every LLM call has a 20-second timeout, one retry and a deterministic fallback. Failures never raise to the API caller.
- Extraction cache: data/cache/extractions/<sha256 of transcript>.json. DEMO_MODE is cache_first or offline.
- Prompt texts are in KIRO_PROMPTS.md Appendix A–D. Copy them verbatim into backend/app/llm/prompts.py.

## Frontend
- React + TypeScript (strict) from the Vite react-ts template, Tailwind CSS v3, Leaflet + react-leaflet, Zustand, react-router-dom. No other UI, chart or component libraries.
- frontend/src/api/types.ts mirrors backend/app/contracts.py field for field.
- Dark dispatch-console theme. Priority colors: red at 80+, amber 50–79, slate below 50.

## Commands
- Backend: `python run.py` (port 8080, docs at /docs). Tests: `pytest -q` from the repo root.
- Frontend: `npm run dev` in frontend/ (port 5173; Vite proxies /api and /ws to 8080).
- Production: one container; FastAPI serves frontend/dist at / with SPA fallback; Cloud Run with --max-instances 1.
```

**`.kiro/steering/structure.md`**

```markdown
---
inclusion: always
---

# Structure and lane ownership

The repository layout is in README.md, section "Repository layout".

Three teammates work in parallel lanes. Only create or edit files in your own lane unless a task explicitly says otherwise. If a change is needed in another lane, stop and describe what is needed instead of editing.

## Lane A — core-pipeline
backend/app/contracts.py, backend/app/config.py, backend/app/audit.py, backend/app/graph/, backend/app/pipeline/locate.py, link.py, weigh.py, priority.py, dispatch.py, orchestrator.py, data/ma/, data/dispatch_rules.json, backend/requirements.txt, pytest.ini, and every test in backend/tests/ except test_extract.py, test_verify.py and test_api.py.

## Lane B — api-llm-realtime
backend/app/llm/, backend/app/pipeline/extract.py, verify.py, backend/app/api/, backend/app/realtime/, backend/app/sim/, backend/app/main.py, run.py, scripts/, data/scenarios/, data/cache/, backend/tests/test_extract.py, test_verify.py, test_api.py.

## Lane C — console-ui
frontend/, Dockerfile, .dockerignore.

## Interfaces between lanes
- A provides: pipeline.orchestrator.process_call(call: CallIn) -> ProcessResult; confirm_link(call_id) -> ProcessResult; split_call(call_id) -> ProcessResult. graph.views: queue(), incidents(), incident_detail(id), call_detail(id), explain(call_id), metrics(), create_lead(...), update_lead(...). config.get_runtime() / update_runtime(patch). audit.log(...) / audit.events(). graph.store.reset().
- B provides: pipeline.extract.extract(call: CallIn) -> Extraction; pipeline.verify.ground(extraction: Extraction, transcript: str) -> list[ClaimStatus] (one status per claim, same order).
- C uses only the HTTP and WebSocket API in README.md.
- contracts.py affects everyone: announce any change to the team before making it.
```

**`.kiro/steering/spec-rules.md`**

```markdown
---
inclusion: always
---

# Spec rules (keep specs small to save credits)

- requirements.md: at most 8 requirements, at most 3 EARS acceptance criteria each. No background or glossary sections.
- design.md: point to README.md sections instead of restating them. No diagrams, no alternatives discussion, no test-plan section.
- tasks.md: at most 8 top-level tasks, at most 2 sub-tasks each. No optional tasks. Put the tests a task needs inside that task. Order tasks so the code runs after each one.
- Implement exactly the formulas, defaults, field names, endpoints and demo outcomes in README.md.
- Never create files outside your lane (see structure.md).
```

**Done when:** all four files are pushed.

### 0.3 Scenario data — B · Claude chat (not Kiro) · 0 Kiro credits

Paste this into a Claude chat, then save the three code blocks as `data/scenarios/mass_ave_robbery.json`, `pike_crash.json` and `washington_st.json`.

```text
Generate synthetic 911 call data for a hackathon prototype called Nexus911. Everything is fictional. Output exactly three JSON files, each in its own code block, and nothing else.

Format of each file:
{
  "scenario_id": "<file name without .json>",
  "title": "<short title>",
  "start_time": "<ISO 8601 with -04:00 offset>",
  "calls": [
    {
      "id": "c01",
      "t_offset_s": 0,
      "transcript": "<caller's words only, no operator lines>",
      "channel": "voice",
      "caller_hash": "<unique id per caller>",
      "caller_role_hint": "victim | witness | bystander | child | official | unknown",
      "device_lat": 42.0,
      "device_lng": -71.0,
      "psap_id": "<id>",
      "transferred_from": null,
      "truth_incident": "A",
      "truth_new_info": false
    }
  ]
}

General rules
- Transcripts are 2–5 short sentences, first person, stressed but clear. Each fact listed below must appear in plain words in that caller's transcript.
- The location is where the emergency happened or where the caller is. When a suspect flees, describe the direction separately ("he ran toward ...").
- Use the coordinates given. Add up to ±0.0003 random jitter to device locations unless told otherwise. Use null when told the device location is missing.
- caller_hash is unique per caller unless stated.
- truth_new_info is true only where stated; otherwise false.

FILE 1: mass_ave_robbery.json
start_time 2026-10-24T14:00:00-04:00, psap_id "boston-ecc", truth_incident "A" unless stated.
Anchor: Massachusetts Ave & Boylston St, Boston (42.3470, -71.0874). c01–c09 and c11 say they are at or near the store at Mass Ave and Boylston, with device locations at the anchor.
- c01 t=0, victim (store clerk): armed robbery just happened at my convenience store at Mass Ave and Boylston; a man in a white jacket and jeans took the cash and ran toward Hynes station. truth_new_info true.
- c02 t=40, witness: man in a white jacket, thin build, ran up Mass Ave toward Newbury.
- c03 t=70, bystander, caller_hash "rep-1": the man ran out of the store in a black jacket.
- c04 t=100, witness, transcript in Spanish: white jacket ("chaqueta blanca"), ran toward the station.
- c05 t=130, unknown role, hearsay only: "my neighbor told me the guy had a black jacket"; the caller did not see it.
- c06 t=160, witness: white jacket and a gray backpack.
- c07 t=190, bystander, caller_hash "rep-1" (same caller as c03): calling again, it was a black jacket.
- c08 t=220, witness: white jacket, heading toward Hynes.
- c09 t=260, bystander: saw the man in the white jacket, nothing new.
- c10 t=360, witness, device at Mass Ave & Newbury St (42.3485, -71.0878), no jitter: "the guy from the store just pulled a knife on someone at Mass Ave and Newbury". Do not mention jacket color. truth_new_info true.
- c11 t=400, witness: white jacket, nothing new.
- c12 t=720, witness, device on Westland Ave (42.3446, -71.0880), no jitter: smoke pouring from a third-floor window on Westland Ave, people trapped and screaming. Do not mention the robbery. truth_incident "B", truth_new_info true.
Jacket colors must be exactly: white in c01, c02, c04, c06, c08, c09, c11; black in c03, c05, c07; none in c10 and c12.

FILE 2: pike_crash.json
start_time 2026-10-24T08:00:00-04:00, psap_id "msp-pike", truth_incident "C" for all calls.
Anchor: I-90 eastbound near Exit 63 (old Exit 8), Palmer (42.1730, -72.3280). Twelve calls p01–p12 at t = 0, 30, 55, 80, 110, 140, 170, 200, 240, 300, 330, 380. Device locations within 500 m of the anchor; p06 and p09 have null device locations.
- Two-car crash: a silver SUV and a red pickup. p01, p03, p05, p07, p08, p11 say "silver SUV"; p02, p04, p06, p12 say "white SUV"; p09 and p10 don't give the SUV's color.
- Location wording: p01 "Pike eastbound right before exit 63"; p02 "near old exit 8 in Palmer"; p04 "around mile marker 62"; p07 "Mass Pike near Palmer"; p08 "the Turnpike eastbound"; the others vary but stay on the Pike eastbound near Palmer.
- p01 truth_new_info true (first call).
- p03 (t=55): the pickup driver isn't moving. No earlier call mentions injuries. truth_new_info true.
- p05 (t=110): channel "text", very short with abbreviations, e.g. "crash pike eb palmer silver suv red pickup".
- p06 (t=140): transcript in Portuguese.
- p07 (t=170): transferred_from "palmer-local".
- p10 (t=300): "the SUV is on fire now". No earlier call mentions fire or smoke. truth_new_info true.

FILE 3: washington_st.json
start_time 2026-10-24T22:00:00-04:00. No caller names a town.
- w01 t=0, witness, psap_id "boston-ecc", device at Washington St, Downtown Crossing, Boston (42.3555, -71.0605): two men fighting on Washington Street. truth_incident "D", truth_new_info true.
- w02 t=60, witness, psap_id "brookline-local", device at Washington St, Brookline Village (42.3326, -71.1166): a fight outside a bar on Washington Street. truth_incident "E", truth_new_info true.
- w03 t=120, bystander, psap_id "boston-ecc", device null: a fight on Washington Street and one guy has a bottle. truth_incident "D", truth_new_info true.
- w04 t=150, witness, psap_id "boston-ecc", device at Downtown Crossing (42.3555, -71.0605): the fight on Washington near Downtown Crossing, someone is bleeding now. truth_incident "D", truth_new_info true.
```

**Done when:** this passes and the files are pushed:

```bash
python -c "import json,glob; [json.load(open(f)) for f in glob.glob('data/scenarios/*.json')]; print('ok')"
```

### 0.4 Contracts — A · Kiro Vibe · ~40 credits

```text
Create these files exactly from README.md and nothing else:
1. backend/app/contracts.py: every model and enum in README "Data contracts", Pydantic v2, Literal types for every enum, defaults as listed.
2. backend/app/config.py: Settings (pydantic-settings, reads .env) with every variable in README "Configuration"; RuntimeSettings exactly as in "Data contracts", initialized from Settings, with module-level get_runtime() and update_runtime(patch) that return copies.
3. Empty __init__.py files for app, app.graph, app.pipeline, app.llm, app.api, app.realtime and app.sim.
4. backend/requirements.txt: fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, networkx, h3>=4, anthropic, httpx, pytest.
5. pytest.ini at the repo root with pythonpath = backend and testpaths = backend/tests.
Do not create any other files.
```

**Done when:** this runs, and A pushes immediately so B and C can pull:

```bash
python -c "import sys; sys.path.insert(0,'backend'); import app.contracts, app.config; print('ok')"
```

### 0.5 Interface stubs — B · Manual · 0 credits (after 0.4 is pushed)

```python
# backend/app/pipeline/extract.py  (STUB, replaced in Lane B task B-2)
from app.contracts import CallIn, Extraction


def extract(call: CallIn) -> Extraction:
    raise NotImplementedError("Lane B")
```

```python
# backend/app/pipeline/verify.py  (STUB, replaced in Lane B task B-3)
from app.contracts import ClaimStatus, Extraction


def ground(extraction: Extraction, transcript: str) -> list[ClaimStatus]:
    raise NotImplementedError("Lane B")
```

**Done when:** both files are pushed.

### 0.6 Frontend scaffold — C · Manual · 0 credits

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom zustand leaflet react-leaflet
npm install -D @types/leaflet tailwindcss@3 postcss autoprefixer
npx tailwindcss init -p
cd .. && git add frontend && git commit -m "frontend scaffold" && git push
```

### 0.7 Types and mocks — C · Kiro Vibe · ~80 credits

```text
In frontend/ only:
1. src/api/types.ts: TypeScript types mirroring README "Data contracts" field for field, with string unions for enums.
2. src/mocks/: queue.json (8 QueueItems covering the auto, suggest, new and confirmed bands, one NEW INFO item with override_reasons ["new_weapon"], one "es" and one "pt" language), incidents.json (3 IncidentSummary items at README "Demo anchor coordinates"), incident.json (an IncidentDetail for the Mass Ave robbery with upper_clothing_color white 0.83 / black 0.17, one contested attribute, one contradiction, one transfer, a DispatchPackage and two leads), call.json (CallDetail), explain.json, ask-next.json, briefing.json, metrics.json, settings.json and sim-status.json.
3. Tailwind v3: content paths for index.html and src/**/*.{ts,tsx}; dark base styles in src/index.css; import "leaflet/dist/leaflet.css" in src/main.tsx.
4. vite.config.ts: dev proxy "/api" → http://localhost:8080 and "/ws" → ws://localhost:8080 with ws: true.
No components yet.
```

**Done when:** `npm run dev` starts without errors.

---

## Step 1 — Create the three specs (0:20–0:35)

Pull first. Open a new **Spec** session in Kiro, paste your prompt, and approve the generated documents unless they contradict README.md. Compare the generated `tasks.md` with the expected list. If it's very different, send one message: "Rewrite tasks.md to match this list:" followed by the list.

### A1 — `core-pipeline` · Kiro Spec · ~80 credits

```text
Create a spec named "core-pipeline" for Lane A (see .kiro/steering/structure.md). README.md is the source of truth; follow spec-rules.md.

Already in the repo: backend/app/contracts.py and config.py, Lane B stubs pipeline/extract.py and pipeline/verify.py, and data/scenarios/*.json.

Build:
1. Data files, each with at most 12 entries, using only the coordinates in README "Demo anchor coordinates":
   - data/ma/gazetteer.json: streets and intersections with town, plus aliases (Mass Ave → Massachusetts Ave, St/Street, Ave/Avenue).
   - data/ma/highways.json: I-90 entries {route, new_exit, old_exit, mile, town, lat, lng} for Exit 63/old 8 (Palmer) and Exit 49/old 5 (Chicopee), plus route aliases (Pike, Mass Pike, Turnpike, 90 → I-90; 128, 95 → I-95).
   - data/ma/landmarks.json: Hynes station and Symphony station (agency hint MBTA Transit Police), Northeastern University (campus police), Downtown Crossing (area, Washington St Boston coordinates), Brookline Village (area, Washington St Brookline coordinates).
   - data/ma/agencies.json: boston-pd, brookline-pd, somerville-pd, cambridge-pd, arlington-pd, palmer-pd, chicopee-pd, state-police, mbta-transit-police, northeastern-police, boston-fire, boston-ems, local-fire, local-ems.
   - data/dispatch_rules.json, first match wins: fire+trapped → 3 Engine, 1 Ladder, 2 EMS, 1 Police; fire → 2 Engine, 1 Ladder, 1 EMS; vehicle_crash+highway+injuries → 2 EMS, 1 Fire, State Police; vehicle_crash+highway → 1 Fire, State Police; vehicle_crash+injuries → 1 EMS, 1 Fire, 1 Police; shooting|stabbing|robbery|assault + weapon → 3 Police, 1 EMS standby; robbery|assault → 2 Police; medical+not_breathing → 2 EMS (ALS), 1 Fire; medical → 1 EMS; default → 1 Police.
2. graph/store.py: GraphStore on networkx.MultiDiGraph with the nodes and edges in README "Knowledge graph", plus reset(). audit.py: in-memory audit log.
3. pipeline/locate.py exactly as README "3. Locate".
4. pipeline/link.py exactly as README "4. Link", including renormalization, perceptual vs identifying attributes, both gates, bands, mass-event mode, the same-PSAP rule for ambiguous locations, tie-breaks and provisional suggest links.
5. pipeline/weigh.py exactly as README "5. Weigh".
6. pipeline/priority.py exactly as README "6. Prioritize".
7. pipeline/dispatch.py exactly as README "7. Dispatch".
8. pipeline/orchestrator.py (process_call, confirm_link, split_call) and graph/views.py (queue, incidents, incident_detail, call_detail, explain, metrics, create_lead, update_lead), writing an audit entry for every link decision and override. process_call runs extract → ground → locate → link → weigh → prioritize → dispatch.

Tests (pytest, no network; build Extraction objects directly, never call extract()):
- locate: old exit 8 and new exit 63 on I-90 resolve to the same point; "Washington St" with a Brookline device location resolves to Brookline; with no town and no device it is ambiguous with confidence 0.3.
- link: a duplicate at the same intersection is auto; incompatible types cap at 0.49; an ambiguous location caps at suggest; mass-event mode raises the auto threshold.
- weigh: 7 white (roles victim, 5 witnesses, bystander) vs 3 black (bystander; unknown hearsay; repeat bystander) gives white ≈ 0.83 and black ≈ 0.17, not contested.
- priority: the three rows in README "Worked example".
```

Expected `tasks.md`:

1. Data files (gazetteer, highways, landmarks, agencies, dispatch rules)
2. GraphStore and audit log
3. Locate, with tests
4. Link, with tests
5. Weigh, with tests
6. Priority, with tests
7. Dispatch
8. Orchestrator and views, with an orchestrator test using hand-built extractions

### B1 — `api-llm-realtime` · Kiro Spec · ~80 credits

```text
Create a spec named "api-llm-realtime" for Lane B (see .kiro/steering/structure.md). README.md is the source of truth; follow spec-rules.md.

Already in the repo: backend/app/contracts.py and config.py (Lane A) and data/scenarios/*.json. Lane A is building pipeline.orchestrator and graph.views in parallel: code against the interfaces in structure.md and use fakes in tests only.

Build:
1. llm/client.py: call_tool(model, system, user, tool_name, input_schema) → dict | None, with forced tool_choice, temperature 0, a 20-second timeout and one retry; returns None on any failure. llm/prompts.py: copy KIRO_PROMPTS.md Appendix A–C verbatim, with tool input schemas generated from the contract models (Extraction, AskNext, Briefing).
2. pipeline/extract.py exactly as README "1. Extract": SHA-256 cache in data/cache/extractions, DEMO_MODE cache_first or offline, caller_role_hint override, and a minimal fallback (incident_type "other", no claims, summary = first 20 words).
3. pipeline/verify.py exactly as README "2. Verify". It must work for Spanish and Portuguese (Unicode casefold, accents kept, punctuation stripped).
4. realtime/bus.py: EventBus and WebSocket manager; WebSocket route /ws/dashboard; DashboardEvent types from README.
5. API routes exactly as README "API" (except /api/agent/turn) in api/routes_*.py, delegating to the orchestrator and graph views and publishing the matching DashboardEvent after every state change. main.py: routers, CORS from env, and serving frontend/dist at / with SPA fallback when the folder exists. run.py at the repo root: uvicorn "app.main:app" with app_dir="backend" and the port from env.
6. Ask-next and briefing endpoints with CLAUDE_MODEL_FAST, prompts from Appendix B and C, an in-memory cache keyed by (id, incident last_seen), the template fallbacks in Appendix B and C, the "missing" rules in Appendix B, and a plain-English label map for attributes (upper_clothing_color → "their jacket or top", vehicle_color → "the vehicle's color", and so on).
7. sim/replay.py and routes: POST /api/simulation/start {scenario_id, speed}, POST /api/simulation/stop, POST /api/reset. Simulated clock: received_at = start_time + t_offset_s; real sleep of the offset difference divided by speed; process_call in-process; publish call.processed and a sim.status event (with t_offset_s and sim_time) after every call.
8. scripts/precompute_extractions.py (fills the cache for every scenario call, skipping cached ones) and scripts/evaluate.py (metrics in README "Evaluation", printed as a markdown table). Both insert backend/ into sys.path.

Tests (no network, LLM mocked): verify (exact match, partial match, hallucinated quote, Spanish quote); extract (cache hit, offline fallback); api (POST /api/calls then GET /api/queue with a fake orchestrator).
```

Expected `tasks.md`:

1. LLM client and prompts
2. Extract with cache, modes and fallback, with tests
3. Verify, with tests
4. EventBus and WebSocket
5. API routes, main.py and run.py, with API tests
6. Ask-next and briefing
7. Simulation replay and reset
8. Precompute and evaluate scripts

### C1 — `console-ui` · Kiro Spec · ~80 credits

```text
Create a spec named "console-ui" for Lane C (see .kiro/steering/structure.md). README.md is the source of truth; follow spec-rules.md.

Already in the repo: a Vite react-ts app in frontend/ with Tailwind v3, react-leaflet, zustand and react-router-dom; src/api/types.ts and src/mocks/*.json; a Vite proxy for /api and /ws.

Build:
1. Data layer: src/api/client.ts (typed functions for every endpoint in README "API"; VITE_USE_MOCKS=true serves src/mocks), src/hooks/useDashboardSocket.ts (auto-reconnect; on each event refetch the queue, incidents, the selected incident and metrics), src/store.ts (Zustand: queue, incidents, selectedIncidentId, selectedCallId, settings, simStatus, connected).
2. App shell: routes /operator (default), /officer and /sim; a top bar with nav, a connection dot and the sim T+ clock; dark console theme.
3. Operator queue and map: QueueCard (priority pill red at 80+, amber 50–79, slate below 50; band chip AUTO/SUGGEST/NEW/CONFIRMED; NEW INFO badge listing override_reasons; language, channel and role chips; location label; summary; T+). Leaflet map with OpenStreetMap tiles, incident markers colored by severity and sized by call count, click to select.
4. Operator incident panel: header (type, severity, location label and confidence, T+ first call, T+ dispatch-ready), TransferBanner, ConsensusBars (every value with share %, sources and first-hand sources; contested attributes highlighted), Contradictions, and a calls list with a "Why linked?" modal (components, weights, gates, decided_by) and Confirm and Split buttons.
5. Operator assist: AskNextPanel for the selected call (confirm line and questions; highlight the town question when the location is ambiguous) and DispatchPackageCard (fields with confidence and sources, contested marker, recommended units, agencies, and an "Illustrative" label).
6. Officer page: incident list, BriefingCard (known / disputed / open), DispatchPackageCard, and a LeadsBoard (suggested → open → assigned → cleared, with accept, assign-unit text and clear).
7. Sim page: scenario picker (mass_ave_robbery, pike_crash, washington_st), speed (1×, 5×, 10×, 20×), Start, Stop and Reset, a mass-event toggle, threshold sliders with "Apply & Replay" (PUT settings, reset, start), and a MetricsPanel (calls, incidents, collapse rate, band counts, NEW INFO calls, verified / pending / rejected claims).
8. Dockerfile (multi-stage: node builds frontend/dist; python:3.11-slim installs backend/requirements.txt and runs `python run.py` on port 8080) and .dockerignore.

Bars are plain divs; no chart library. Keep components small and typed.
```

Expected `tasks.md`:

1. Data layer
2. App shell and routing
3. Queue and map
4. Incident panel and Why-linked modal
5. Ask-next panel and dispatch card
6. Officer page
7. Sim page
8. Dockerfile

---

## Step 2 — Build (0:35–2:30)

Run your tasks in order with **Start task**, and commit after each one.

| Lane | Done when |
|---|---|
| A | `pytest -q` passes for locate, link, weigh, priority and orchestrator tests |
| B | `pytest -q` passes for verify, extract and API tests; `python run.py` starts; `/docs` lists every README endpoint |
| C | With `VITE_USE_MOCKS=true`, all three pages render from mocks with no console errors |

If a task fails, use the fix template at the end of this file rather than open-ended chat.

---

## Step 3 — Integrate (2:30–3:15)

### I1 — Wire the API to the real pipeline — B · Kiro Vibe · ~60 credits

```text
Lane A's orchestrator and graph views are merged. Remove any fakes outside tests and wire every route to the real modules. Start the app, POST the first three calls of data/scenarios/mass_ave_robbery.json to /api/calls, and fix any contract mismatches in Lane B files only. If a fix is needed in a Lane A file, stop and list it instead of editing.
```

### I2 — Precompute extractions — B · Manual · 0 credits

```bash
python scripts/precompute_extractions.py      # needs ANTHROPIC_API_KEY in .env
git add data/cache && git commit -m "cached extractions" && git push
```

If one extraction is clearly wrong (for example, a missing jacket color), delete that cache file and rerun the script, or correct the JSON by hand. It's synthetic data.

### I3 — Live data in the UI — C · Kiro Vibe · ~80 credits

```text
Set VITE_USE_MOCKS=false. With the backend running, start the mass_ave_robbery replay at 10× from /sim. Fix any rendering errors or type mismatches between src/api/types.ts and the live API; backend/app/contracts.py is the authority. Edit frontend/ only.
```

### I4 — Scenario acceptance tests — A · Kiro Vibe · ~80 credits (after I2)

```text
Add backend/tests/test_scenarios.py that replays every scenario in-process with DEMO_MODE=offline (cached extractions only) and asserts the outcomes in README "Demo scenarios":
- mass_ave_robbery: c01–c11 end in one incident; upper_clothing_color white share is between 0.75 and 0.90 with black still listed; c10 has new_info with "new_weapon" and priority ≥ 90; c12 creates a new incident with priority 100 and is first in the queue.
- pike_crash: all calls in one incident; agencies include State Police; one transfer from palmer-local; the SUV color lists both silver and white; p03 has "new_injury"; p10 has "new_hazard".
- washington_st: w01 and w02 are different incidents; w03 has band "suggest", an ambiguous location, and w01's incident; w04 is in w01's incident with "new_injury".
Run pytest and fix failures in Lane A files only. If a failure comes from a cached extraction, list the call id and the wrong field instead of editing data/cache.
```

**Done when:** `pytest -q` is green and the robbery replay looks right in the browser.

---

## Step 4 — Evaluate, polish, deploy (3:15–4:00)

### P1 — Evaluate — B · Manual · 0 credits

```bash
python scripts/evaluate.py
```

Paste the table into README "Evaluation". Report only what the script printed.

### P2 — Demo polish — C · Kiro Vibe · ~80 credits

```text
Demo polish in frontend/ only:
1. When a call becomes first in the queue, briefly highlight its card.
2. Show a small toast for every NEW INFO call, with its reasons.
3. Make /operator fit a 1440×900 screen without page scrolling (panels scroll internally).
4. In the Why-linked modal, show the gate name in plain words, for example "Different emergency types are never merged".
Do not change the data layer.
```

### P3 — Deploy — C · Manual · 0 credits

```bash
docker build -t nexus911 . && docker run --rm -p 8080:8080 --env-file .env nexus911   # local check
gcloud run deploy nexus911 --source . --region us-east1 --allow-unauthenticated \
  --max-instances 1 --timeout 3600 \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,DEMO_MODE=cache_first"
```

Put the URL at the top of README.md.

### P4 — README finish — A · Manual · 0 credits

Fill in the team names, hackathon name, demo URL and video link, and confirm the evaluation table matches the script output.

---

## Step 5 — Stretch (4:00–4:30, only if the calibration gate allows)

### S1 — Live caller chat — C · Kiro Vibe · ~70 credits

```text
Add a CallerChat panel to /sim in frontend/ only: a textarea for a text-to-911 message, a location dropdown (README "Demo anchor coordinates" plus "No location"), and a Send button that POSTs /api/calls with channel "text", a random caller_hash, received_at = simStatus.sim_time if a replay has run (otherwise now), and the chosen device coordinates. Show the returned priority, band and incident id.
```

This needs `DEMO_MODE=cache_first` and an API key, because new messages aren't in the cache.

### S2 — Corroboration agent — B · Kiro Vibe · ~120 credits

```text
Add the stretch corroboration agent (README "Features" S2, KIRO_PROMPTS.md Appendix D):
- backend/app/llm/agent.py: run the code-level keyword guard from Appendix D first; otherwise call CLAUDE_MODEL_FAST with the Appendix D prompt and the record_agent_turn tool. Any failure escalates.
- POST /api/agent/turn {session_id, incident_id, caller_text} → {action, message, reasons}. Sessions live in memory; the first agent message is the fixed opening from Appendix D; at most 3 questions. On "complete", submit the combined caller text as one CallIn (channel "text", caller_hash = session_id) through process_call. On "escalate", publish DashboardEvent "agent.escalated" with the session transcript.
Tests with the LLM mocked: keyword escalation, model-failure escalation, completion after 3 answers.
```

Then C adds a small agent panel (~50 credits):

```text
In frontend/ only, add an AgentPanel to /sim: pick an incident, type caller replies, show agent messages, and on "escalate" show a red "Escalated to call-taker" banner. On /operator, show a toast for every agent.escalated event.
```

---

## Step 6 — Freeze (4:30–5:00)

- `pytest -q` is green and the evaluation table is in README.md.
- Two full dry runs of the three-minute demo script, with `/api/reset` between runs.
- One run with Wi-Fi off and `DEMO_MODE=offline` to prove the demo survives bad venue internet.
- Record the demo as a backup video.
- Final push and tag: `git tag v2-demo && git push --tags`.

---

## Fix template

Use this instead of open-ended chat. It keeps each fix small and cheap.

```text
Bug in Lane <A|B|C>: <one-line symptom>.
Expected (README.md → <section>): <exact rule, value or outcome>.
Observed: <error message or wrong output>.
Fix only in <file(s)>. Do not refactor or touch other files. Add or update one test that reproduces it.
```

---

## Appendix A — Extraction prompt (`record_extraction`)

Tool: `record_extraction`, description "Record the structured facts from one 911 call.", input schema = the `Extraction` model.

**System prompt**

```text
You extract structured facts from one 911 call transcript (a voice transcript or a text-to-911 message) for an emergency-dispatch knowledge graph. You only record what this caller said. You never decide whether the call is a duplicate.

Rules
1. Record only what the caller states. Never infer, guess or add facts. If unsure, leave the claim out.
2. Every claim needs "quote": a span copied character-for-character from the transcript, in the transcript's original language, that states the fact. Do not translate, paraphrase or correct the quote.
3. "value" is canonical English, lowercase, 1–3 words. Colors use basic names (white, black, gray, silver, red, blue, green, yellow, brown, orange, purple). sex is male or female. build is thin, medium or heavy. age_range looks like "20s". weapon is knife, gun, bottle, bat or other. vehicle_type is suv, pickup, sedan, van, truck, motorcycle or bicycle. victim_condition is not_moving, unconscious, bleeding, not_breathing or injured. hazard is fire, smoke, fuel_leak or downed_wires. injury_count and people_count are digits.
4. Subjects: suspect, suspect_2, vehicle, vehicle_2, victim, scene. "suspect" is the main suspect; use suspect_2 only for a clearly different second person. In a crash, use vehicle and vehicle_2 for the two vehicles.
5. Attributes: upper_clothing_color, upper_clothing_type, lower_clothing, hair, build, height, age_range, sex, weapon, direction_of_travel, suspect_location, vehicle_make, vehicle_model, vehicle_color, vehicle_plate, vehicle_type, injury_count, victim_condition, people_count, hazard. Use no others.
6. first_hand is true only when the caller personally saw or heard it. It is false for hearsay such as "my neighbor said", "someone told me" or "I heard that".
7. caller_role: victim (harmed or directly targeted, including a store clerk who was robbed), witness (saw it directly), bystander (nearby with a partial view), child (says or makes clear they are under 18), official (on-duty police, fire, EMS or security), otherwise unknown.
8. incident_type: shooting, stabbing, robbery, assault, medical, fire, vehicle_crash, disturbance, suspicious_activity or other. Pick the most severe type this caller reports.
9. flags: set true only when stated: weapon_present, injuries_reported, not_breathing, fire_or_smoke, trapped, child_involved.
10. location is where the emergency happened or where the caller is, never only where a suspect fled (put that in direction_of_travel). Fill only what was said: street, cross_street, town, landmark (for example "Hynes station", "Downtown Crossing", "Northeastern"), highway_route ("the Pike", "Mass Pike", "Turnpike" → "I-90"; "128" → "I-95"), highway_direction (EB, WB, NB, SB), highway_exit (digits only, as said), exit_is_old (true if the caller says "old exit"), mile_marker, and raw (the caller's location words copied verbatim).
11. language: the ISO 639-1 code of the transcript (en, es, pt, ht, zh, vi and so on).
12. summary: at most 20 words, English, neutral.
Respond only by calling record_extraction.
```

**User message**

```text
Channel: {channel}
Transcript:
<<<
{transcript}
>>>
```

## Appendix B — Ask-next prompt (`record_ask_next`)

Tool: `record_ask_next`, input `{confirm_line: string, questions: string[]}` with 2–3 questions.

**System prompt**

```text
You help a 911 call-taker decide what to ask next. Write short, calm, plain-English prompts the call-taker can say aloud.

Rules
1. Never tell the call-taker to end, skip, shorten or deprioritize a call. Never give medical or tactical instructions.
2. confirm_line: one sentence that confirms place and time only, never descriptions. Example: "We have reports near Mass Ave and Boylston. Are you there now?" If link_band is "new", confirm_line is "".
3. questions: 2–3 open-ended questions, at most 15 words each, in this priority order: (a) if the location is ambiguous, ask which town or the nearest cross street; (b) for contested attributes, ask the caller to describe it without naming any option; (c) missing critical facts; (d) "What is happening right now?"
4. Never put a possible answer inside a question. Ask "What color was the jacket?", not "Was the jacket white?".
5. Adapt to caller_role: child → very simple words, one idea per question; victim → start with "Are you safe right now?"; official → brief and factual.
Respond only by calling record_ask_next.
```

**User message** (JSON built by the backend)

```json
{
  "caller_role": "witness",
  "call_summary": "...",
  "link_band": "auto",
  "known_facts": [{"attribute": "upper_clothing_color", "top_value": "white", "share": 0.83}],
  "contested": [{"attribute": "vehicle_color", "values": ["silver", "white"]}],
  "missing": ["weapon", "direction_of_travel"],
  "location": {"label": "Washington St", "confidence": 0.3, "ambiguous": true, "candidates": ["Boston", "Brookline", "Somerville"]}
}
```

**"missing" rules (computed by the backend):** violent types → weapon, upper_clothing_color, direction_of_travel; vehicle_crash → injury_count, vehicle_type; fire → people_count, hazard; medical → victim_condition. A fact is missing when the incident consensus has no value for it.

**Template fallback:** confirm_line = "We have a report near {location label}. Are you there now?" ("" for band new). Questions: "Which town are you in?" if the location is ambiguous; then "Can you describe {plain label}?" for the first contested attribute; then "What is happening right now?"

## Appendix C — Briefing prompt (`record_briefing`)

Tool: `record_briefing`, input `{known: string, disputed: string, open: string}`.

**System prompt**

```text
You write a three-line briefing for responding officers from a structured incident record.

Rules
1. Use only facts in the input. Do not add, infer or soften anything.
2. known: at most 25 words, the facts with share ≥ 0.70, each with its percentage and source count, for example "white jacket (83%, 7 sources)".
3. disputed: at most 25 words, the contested attributes with each value and share, or "None".
4. open: at most 25 words, the critical facts still unknown and the most recent change.
5. No speculation about identity, motive or guilt.
Respond only by calling record_briefing.
```

**User message:** the incident's consensus, contradictions, dispatch package and last five timeline events as JSON.

**Template fallback:** build the three lines directly from the consensus using the same rules.

## Appendix D — Corroboration agent prompt (`record_agent_turn`, stretch)

Tool: `record_agent_turn`, input `{action: "ask" | "escalate" | "complete", message: string, reasons: string[]}`.

**Fixed opening** (sent by the system, not the model):

```text
You're connected to 911. A call-taker is monitoring this conversation and can join at any moment.
```

**System prompt**

```text
You assist a caller who is waiting in a 911 queue during a surge, while all call-takers are busy. A human call-taker monitors every conversation and can take over at any time. You do not replace the call-taker.

Goal: confirm whether the caller is reporting the known incident, collect anything new, then hand off.

Rules
1. Ask one short open question at a time, at most three in total, in this order: where exactly are you; what do you see right now; is anyone hurt.
2. Escalate immediately (action "escalate") if the caller mentions injury, bleeding, not breathing, unconsciousness, a weapon, fire or smoke, someone trapped, a child in danger, their own danger, a location that doesn't match the incident, a different emergency, distress or confusion, or asks for a person. Escalate whenever you are unsure.
3. Never give medical, legal or tactical advice. Never tell the caller to hang up. Never promise or deny that help is coming.
4. After three answers with no escalation trigger, the action is "complete" and the message thanks the caller and says a call-taker has their information.
Respond only by calling record_agent_turn.
```

**User message** (JSON)

```json
{
  "incident_summary": "...",
  "incident_location": "...",
  "questions_asked": 1,
  "conversation": [{"role": "agent", "text": "..."}, {"role": "caller", "text": "..."}]
}
```

**Code-level guard** (runs before the model): escalate without calling the model if the caller text contains any of these, case-insensitive: hurt, bleeding, blood, not breathing, unconscious, gun, knife, weapon, fire, smoke, trapped, child, kid, help me, different, another, herido, sangre, pistola, cuchillo, fuego, humo, atrapado, ferido, sangue, arma, faca, fogo, fumaça, preso. Any model error or invalid output also escalates.
