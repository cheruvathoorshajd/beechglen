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

### Waiting rules (replace all earlier waiting rules)

The loop guard counts partial or non-zero results as failures: `sleep` outlasts the tool's wait, and `grep` exits 1 when it finds nothing. Seven in a row stop the session.

- Start every command with `cd /Users/kaushikj/Desktop/beechglen &&`. One tool call at a time.
- Never use `sleep`, and never wait inside a command.
- Run builds, tests and scripts in the background with the exit marker, e.g.
  `(.venv/bin/python -m pytest -q --durations=10 > .kiro/logs/pytest-full.txt 2>&1; echo "exit=$?" >> .kiro/logs/pytest-full.txt) &`
- Check a background job with one instant line that always succeeds:
  `cd /Users/kaushikj/Desktop/beechglen && if grep -q '^exit=' .kiro/logs/X.txt; then grep -E "error|×|FAIL|Test Files|Tests |exit=|built in" .kiro/logs/X.txt | tail -n 20; else echo "still running"; fi; true`
- If it says "still running", do a file task (e.g. update context.md) before checking again. Never check twice in a row.
- End every command that might find nothing (grep, find, diff) with `; true`.
- test_scenarios.py and evaluate.py drive the flow directly on the simulated clock (no real sleeps); each run finishes in seconds.

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

## Stage 8: design port (KIRO_DESIGN_PROMPTS.md)

Stage 8 (frontend) follows `KIRO_DESIGN_PROMPTS.md` section 2. Sources: `.kiro/steering/style-guide.md` (looks), `design/V2_SCREENS.md` (landing, sign-in, onboarding, console header words and behavior), README.md (behavior, data, endpoints). `design/nexus911-mock.html`, `design/STYLE_GUIDE.html` and `design/PORT_PLAN.md` are for layout, interaction and CSS only. Never run `design/FRONTEND_BUILD_PROMPT.md` (v1 prompt) or copy the mock's v1 wording.

### Recorded design decisions (don't revisit)

- Tailwind 3 stays. Tokens on `:root` in `src/index.css`, mirrored in `tailwind.config.js` `theme.extend` (colors, fontFamily, borderRadius). No Tailwind v4 `@theme`.
- Fonts from @fontsource, imported in `src/main.tsx` (bundled, works offline): `@fontsource-variable/fraunces` (roman + italic, opsz axis if offered), `@fontsource/ibm-plex-sans` 400/500/600/700 + italic 400, `@fontsource/ibm-plex-mono` 400/500. Latin-only files where available. Serif stack `"Fraunces Variable", Fraunces, Georgia, serif`. No Google Fonts link, no Outfit.
- Font packages are the only new dependencies. Icons: inline-SVG `Icon` component from the mock's `<symbol>`s (24×24, 1.8 stroke); new icons only when needed, same style.
- Landing, sign-in and onboarding: the mock's class-based CSS ported to plain `landing.css`, `auth.css`, `onboarding.css`, renaming `--accent`→`--brand`, `--accent-rule`→`--brand-rule`, `--accent-tint`→`--brand-tint`, `--bad`→`--brand`. Field errors use the guide's `.ferr` (white text, crimson ✕), not the mock's crimson `.field-err`. Console components use Tailwind with the theme tokens.
- No backend changes. Sign-in is name only, kept in the browser; guests get every feature.
- Map darkens OSM tiles with a CSS filter on `.leaflet-tile-pane`. Offline, tiles don't load; everything else works.
- Commits: `stage-8.D<N>: <summary>`, local only. After each stage: background build + Vitest, update this file, commit.

### Design checklist

- [x] D1 Foundations: README "Frontend" + tech.md frontend section; font packages; tokens + base styles (body, :focus-visible, text-wrap: balance, reduced motion); primitives in `src/ui/` (Wordmark, Button, Badge, Tag, SpecLabel, ConfidenceBar, Field, Segmented, ChoiceCard, Disc, Bloom, LiveDot, Icon); remove off-palette colors.
- [x] D2 Console: every C1 task (data layer, mocks, shell, queue + map, incident panel + Why linked, ask-next + dispatch, officer, sim) built in the "Console mapping" style; Wordmark in the top bar; Vitest for priority pill thresholds and the Critical badge word.
- [x] D3 Landing at `/` (V2_SCREENS.md); console default `/operator`; CTAs go to `/operator` until D4.
- [x] D4 Session module, route guard, sign-in, console header (who chip, Replay intro, Sign out); Vitest for session.ts (incl. throwing storage), guard redirects, name validation.
- [x] D5 Onboarding wizard; Vitest for Escape skipping, focus to each heading, server-down state.
- [x] D6 Verify: backend suite, build, Vitest (background, exit marker); grep hex/rgb/rgba/Tailwind color utilities outside token files; contrast table; README + context.md; browser checklist.

### Where it stands

- D1 done: `@fontsource-variable/fraunces`, `@fontsource/ibm-plex-sans`, `@fontsource/ibm-plex-mono` 5.3.0 (pinned). Fraunces uses `opsz.css` + `opsz-italic.css` (family "Fraunces Variable", wght 100–900); Plex uses `latin-*` files. Tokens in `src/index.css` (adds `--brand-glow` .30 for the bloom, `--warn-rule`/`--warn-tint` for the prototype notice, `--ground-veil` for the wizard footer), mirrored in `tailwind.config.js` (`rounded` = 3px, `rounded-pill`). Primitives in `src/ui/index.tsx` + `src/ui/Icon.tsx`, styles in `src/ui/ui.css` (imported in main.tsx). Also: `Contested`, `buttonClass()`, `formatShare()`, `nextIndex()` (roving radiogroup keys). No off-palette code existed yet (frontend had only `types.ts`). `src/App.tsx` is a D1 placeholder replaced in D2. Verify: `.kiro/logs/fe-d1.txt` build ✓, Vitest 6/6.
- Frontend commands (repo root): build+test in background `(cd frontend && npm run build > ../.kiro/logs/fe-dN.txt 2>&1 && npx vitest run >> ../.kiro/logs/fe-dN.txt 2>&1; echo "exit=$?" >> ../.kiro/logs/fe-dN.txt) &`, then the wait line.
- D2 done (all C1 tasks built in the new style, so nothing gets restyled later):
  - Mocks (0.7): `scripts/export_mocks.py` writes `frontend/src/mocks/*.json` (10 files) from a real offline replay; `backend/tests/test_frontend_mocks.py` validates them against contracts.py (11 tests). Regenerate after contract changes. The robbery incident mock gets one injected transfer (cambridge-ecc) so the banner shows in mock mode.
  - Data layer: `src/api/client.ts` (every README endpoint; `VITE_USE_MOCKS=true` → dynamic-imported mocks; Vitest sets it via `test.env`), `src/store.ts` (Zustand; `refresh()` collapses bursts), `src/hooks/useDashboardSocket.ts` (reconnect backoff, NEW INFO toasts from `override_reasons`), `src/hooks/useFocusTrap.ts`, `src/lib/format.ts` (reason/gate words, T+, priority tone, Critical = severity ≥ 0.9).
  - Components in `src/components/console/`: `chips.tsx` (PriorityPill, BandChip, CriticalBadge, NewInfoBadge), `QueueCard.tsx`, `IncidentMap.tsx` (react-leaflet, CSS-classed markers), `evidence.tsx` (ConsensusBars, Contradictions, TransferBanner, DispatchPackageCard), `IncidentPanel.tsx` (+ Confirm/Split), `WhyLinkedModal.tsx`, `AskNextPanel.tsx`, `officer.tsx` (BriefingCard, LeadsBoard), `shell.tsx` (TopBar with Wordmark, Toasts, MetricsPanel, ConsoleLayout), `console.css` (Leaflet dark filter, markers, first-in-queue flash). Pages in `src/pages/` (Operator, Officer, Sim).
  - Decision: queue cards use the call's own severity for Critical (else every robbery duplicate would be Critical, since the incident is 0.9); incident cards use incident severity.
  - P2 polish included: first-in-queue highlight, NEW INFO toasts with reasons, /operator panels scroll inside a full-height grid, gates in plain words.
  - `/` redirects to `/operator` until D3. Verify: `.kiro/logs/fe-d2.txt` build ✓, Vitest 17/17 (priority thresholds, Critical word, three pages render from mocks with the map stubbed).
- D3 done: `src/landing/Landing.tsx` + `landing.css` (mock CSS ported; flow is 7 columns → 4 at 980 → 2 at 760 → 1 at 560; table scrolls in `.tbl-wrap`; `.lp { overflow-x: clip }`). Every section is plain markup (no scroll animations). CTAs come from `src/landing/targets.ts` `useStartTargets()`, which returns `/operator` for everything until D4. Colophon: "Built for the hackathon" (README's hackathon name is still a placeholder; `HACKATHON` constant in Landing.tsx) and the GitHub README link. `/` is the landing; console default is `/operator`. Verify: `.kiro/logs/fe-d3.txt` build ✓, Vitest 21/21.
- D4 done: `src/auth/session.ts` (V2_SCREENS.md exports plus `validateName`, `NAME_EMPTY`/`NAME_INVALID`, `useSessionVersion`; storage wrapped in try/catch with an in-memory fallback, so private mode still works), `src/auth/guards.tsx` (`RequireConsole`, `RequireSession`, `SignedOutOnly`, `signOut()`; sign-out navigates to `/` first and the console guard renders nothing while signing out, else it raced to `/signin`), `src/auth/SignIn.tsx` + `auth.css`, `src/auth/SessionControls.tsx` (who chip, Replay intro, Sign out in the TopBar), `src/landing/targets.ts` now session-aware (Get started/Sign in → /signin; with a session "Open the console" → /operator, Run the demo → /welcome; guest card sets a guest session). `src/onboarding/Onboarding.tsx` is a placeholder until D5. Verify: `.kiro/logs/fe-d4b.txt` build ✓, Vitest 45/45 (session incl. throwing storage, guard redirects, name validation, sign-in errors + focus, header controls).
- D5 done: `src/onboarding/Onboarding.tsx` + `onboarding.css` + `onboarding.test.tsx`. Fixed full-screen dialog (role dialog, aria-modal), 280px rail, 2px progress bar, bloom, footer Back · Skip intro · Continue. Step id mirrored in sessionStorage `nexus911:onboarding-step`; focus moves to each step's h1; `useFocusTrap` keeps Tab inside and Escape = Skip; step 3 cards are a radiogroup with arrow keys; `GET /api/metrics` with a 4 s timeout decides server up/down (down: alert + Try again, demo disabled, console selected); the demo does `POST /api/reset` then `POST /api/simulation/start` `{mass_ave_robbery, speed}` with a spinner, "already running" counts as success, failure shows an alert with "Open the console instead". Finish (any path) = markOnboarded, clear step, go to /operator. Verify: `.kiro/logs/fe-d5.txt` build ✓, Vitest 51/51, no warnings.
- D6 done: backend suite `.kiro/logs/d6-pytest.txt` 164 passed; frontend `.kiro/logs/d6-fe.txt` build ✓ and Vitest 51/51. Served check (`python run.py` in the background, then stopped): `/`, `/signin`, `/welcome`, `/operator`, `/officer`, `/sim` → 200 text/html (built index), `/assets/index-*.js` 200, `/api/queue` 200 JSON, `/docs` 200, `/api/nope` 404. README "Frontend" gained build/test commands. Color grep: no hex/rgb()/rgba() in `frontend/src` outside `src/index.css`, and no Tailwind default-palette color utilities (all colors go through the tokens).

### Contrast (WCAG 2.x, computed from the token values)

| Text / element | Background | Ratio | Use | Result |
|---|---|---|---|---|
| ink #FFF | ground #000 | 21.0 | body, headings | pass |
| ink | card #0C0C0C | 19.6 | panels, rail, story panel | pass |
| ink | raised #161616 | 18.1 | selected rows, lead cards | pass |
| ink-soft #A3A3A3 | ground | 8.3 | secondary text, captions, labels | pass |
| ink-soft | card | 7.8 | captions in panels | pass |
| ink-soft | raised | 7.2 | captions on selected rows | pass |
| ink | brand #C00000 | 6.5 | primary button, Critical badge, Tag, 80+ pill, done step | pass |
| warn #EAB308 | ground / card | 11.0 / 10.2 | 50-79 pill, SUGGEST, △ Contested, limits "!" | pass |
| ok #22C55E | ground / card | 9.2 / 8.6 | LIVE, CONFIRMED, dispatch ready | pass |
| ink | warn tint over ground | 19.5 | prototype notice | pass |
| brand | ground | 3.24 | wordmark "911" (≈20px bold = large), icons, dots, rules, borders, focus ring | pass for large/UI only |
| brand | card | 3.02 | wordmark "911" in top bar, rail and story panel; icons | pass for large/UI, barely |
| brand | brand-tint tile over ground | 3.03 | novelty and card icons | pass for UI |
| ink-soft | brand (disc) | 2.57 | must never happen | **fail if it occurs**, so check that no grey text overlaps the disc |

No small crimson text anywhere: errors are white with a crimson ✕, badges with crimson borders use white text.

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
- [x] Stage 7: `scripts/precompute_extractions.py`, `scripts/evaluate.py`; run precompute (I2); `test_scenarios.py` (I4); evaluation table in README (P1)
- [ ] Stage 8: frontend (0.6, 0.7, C-1..C-7, I3, P2) + build + smoke tests + mock/contract check, done as design stages D1–D6 (see "Stage 8: design port")
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

- Stage 7: precompute → 28/28 extracted with claude-sonnet-5-5 (`.kiro/logs/precompute.txt`), re-run after the c03 fix → cached=27 extracted=1. Full suite → `.kiro/logs/pytest-full.txt` exit=0, 153 tests, slowest 0.05 s. `scripts/evaluate.py` (0 cache misses): clustering P/R/F1 1.00/1.00/1.00; new-incident recall 100% (5/5); new-info recall 100% (10/10); collapse 82% (28 → 5); claims 86/0/0; auto 22 / full intake 6. Table is in README "Evaluation".

Note: the user made and pushed commits `6f29abc` ("Latest Kiro Commits") and `744608a` ("nexus911 testing"), which already hold the stage 7 code, scripts, tests, cache and c03 edit. The `stage-7` commit adds the README evaluation table and this file. Agent commits stay local (never push).

## Stage 7 data fix (c03)

c03's transcript ("A man just ran out of the store. He was wearing a black jacket.") never mentioned the robbery, so Claude extracted incident_type `other`. Type score 0.3 gave p_same 0.8225 (< 0.85) → band `suggest`, claims provisional, black jacket excluded from consensus → white share 0.918 (test range 0.75-0.90). Quotes were all verified. Fix (data only, no weights/thresholds/test changes): c03 now says "The man who robbed the store just ran out. He was wearing a black jacket."; stale cache file deleted and re-extracted. White share is now ≈0.83.

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

## Live checks

- `scripts/smoke_check.py` runs against a running server (`python run.py`): every GET read model, `/ws/dashboard` delivering `call.processed`, one never-cached call to prove Claude extraction is live (a few cents), ask-next not being the template, briefing, and confirm. Log: `.kiro/logs/smoke-live.txt`.
- First live run (2026-10-24): all GETs 200, WebSocket delivered `call.processed`, a new transcript was extracted live by claude-sonnet-5-5 in 4.8 s (red hoodie, male, toward Symphony station), ask-next came from claude-haiku-5-5 (not the template).
- The Kiro process list can show `run.py` as "exited" while the server is still listening on 8080; check with `lsof -nP -iTCP:8080 -sTCP:LISTEN`.

## Test conventions

- `backend/tests/conftest.py` forces `DEMO_MODE=offline` and a blank `ANTHROPIC_API_KEY` before any app import, and resets settings and runtime thresholds around every test. No test touches the network.

## Next step

Stage 8: frontend (KIRO_PROMPTS.md 0.7 + C1), one C1 task per commit. Hand-written `frontend/package.json` with pinned versions (Vite 6, React 18, react-leaflet 4, Leaflet 1.9, react-router-dom 6, Zustand 4, Tailwind 3, TypeScript 5, Vitest, @testing-library/react, jsdom); no create-vite. `npm install` in the background with the exit marker. Build against mocks first (VITE_USE_MOCKS=true), then the live API; `backend/app/contracts.py` is the authority for types. Verify each task with a background `npm run build` (exit marker) and a Vitest smoke test rendering each page from the mocks (Leaflet map stubbed).
