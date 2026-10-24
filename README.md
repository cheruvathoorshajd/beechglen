# Nexus911

**A claim-weighted knowledge graph for 911 that links duplicate calls, surfaces what's new, and keeps humans in control.**

Hackathon: `Nexus911` · Focus: Massachusetts · Built with Kiro · FastAPI · Claude · React

 **Demo video:** https://youtu.be/VHyKyrJE-pw · **Team:** Dennis, Kaushik, Arvind

---

## Problem

During a single emergency, 911 centers receive many calls about the same event, and today's systems cannot tell operators which calls repeat known information and which report something new.

When dozens of people witness a crime or crash, every caller is handled as a fresh emergency. Operators re-collect the same location and suspect details, conflicting accounts ("white jacket" vs. "black jacket") have no principled way to be weighed, and a genuinely new incident nearby can wait in the same queue as the tenth duplicate. Officers receive a stream of repeated, unreconciled updates instead of one trustworthy picture.

Massachusetts makes this harder:

- **Fragmented dispatch.** Many local and regional centers answer 911 calls and transfer them between each other (for example, highway calls handled by State Police), so context is lost at every handoff.
- **Duplicate street names.** Washington St, Main St and Massachusetts Ave exist in many towns.
- **Two exit-number systems.** MassDOT converted highway exits from sequential to mile-based numbers, and callers still use both: "old exit 8" and "exit 63" are the same place on the Pike.
- **Many languages and channels.** Callers speak Spanish, Portuguese, Haitian Creole, Cape Verdean Creole, Chinese, Vietnamese and more, and text-to-911 adds short, noisy reports.
- **Surges.** Marathon Monday, July 4th on the Esplanade and nor'easters multiply everything above.

## Solution

Nexus911 turns every call into **quote-grounded claims** in a knowledge graph. It links calls into incidents with an explainable probability, weighs conflicting accounts by reliability, recency and independence rather than raw counts, and gives every call a priority that **rises with new information and falls with repetition**.

- **Operators** see a priority queue, suggested matches with the reasons behind them, and "ask next" prompts. They can confirm or split any link.
- **Officers** get a three-line briefing, a dispatch package with per-field confidence and source counts, and trackable leads.
- **Supervisors** see live load: calls, incidents, how many calls collapsed into existing incidents, and which calls carried new information.

> **Principle: no call is ever dropped.** Nexus911 reorders and annotates the queue; it never hides a call. AI suggests, humans decide, and every decision is logged.

## What's novel

| # | Novelty | What it means in practice |
|---|---|---|
| 1 | **Claim-level knowledge graph** | Every statement is its own node with its caller, verbatim quote and weight, so "7 say white, 3 say black" is preserved and weighed instead of overwritten |
| 2 | **Quote-grounded hallucination guard** | Every AI-extracted fact must cite a verbatim span of the transcript or it is rejected; partial matches flow through as `pending_verification` (fail-open) |
| 3 | **Information-gain priority** | `priority = severity × (1 − P_dup × (1 − novelty))`: repeats sink, new facts rise, and a new weapon, injury, location or hazard always escalates |
| 4 | **Independence-aware witness weighting** | Hearsay and repeat callers count for less, so an echoed rumor can't outvote eyewitnesses (raw 7–3 becomes about 83%–17% in the demo) |
| 5 | **Explainable three-band linking** | Auto-link, suggest or new, with every score component visible and one-click confirm or split by the operator |
| 6 | **Massachusetts-aware resolution** | Town disambiguation for repeated street names, old and new exit numbers, MBTA/campus/State Police routing, cross-PSAP transfer context, multilingual callers |

## Features

| ID | Feature | Module |
|---|---|---|
| F1 | Call intake: voice transcripts and text-to-911, optional device location, PSAP and transfer source | `api/routes_calls.py` |
| F2 | Claim extraction with Claude (forced tool-use JSON, temperature 0, cached by transcript hash) | `pipeline/extract.py` |
| F3 | Quote grounding (hallucination guard) | `pipeline/verify.py` |
| F4 | Massachusetts location resolver: town-aware gazetteer, old/new exits, mile markers, landmarks, device fallback | `pipeline/locate.py` |
| F5 | Incident linking: H3 + time candidates, P(same), three bands, type and location gates | `pipeline/link.py` |
| F6 | Claim weighting, per-attribute consensus, contested flags, contradictions | `pipeline/weigh.py` |
| F7 | Severity, novelty, priority and hard overrides | `pipeline/priority.py` |
| F8 | Dispatch package, recommended units, agency routing, suggested leads | `pipeline/dispatch.py` |
| F9 | Operator console: priority queue, map, incident panel, NEW INFO badge, confidence bars, transfer banner | `frontend/src/pages/Operator.tsx` |
| F10 | "Why linked?" explainer with Confirm and Split overrides (audited) | `api/routes_links.py`, `components/WhyLinkedModal.tsx` |
| F11 | "Ask next" prompts: a confirm line plus 2–3 open questions adapted to caller role and gaps | `api/routes_calls.py`, `llm/prompts.py` |
| F12 | Officer view: three-line briefing, dispatch package, leads board | `frontend/src/pages/Officer.tsx` |
| F13 | Simulation replay with T+ clock, mass-event mode, threshold sliders, live metrics | `sim/replay.py`, `frontend/src/pages/Sim.tsx` |
| F14 | Evaluation script: clustering precision/recall, new-incident recall, collapse rate, guard stats | `scripts/evaluate.py` |
| S1 | Stretch: live text-to-911 caller chat | `frontend/src/pages/Sim.tsx` |
| S2 | Stretch: corroboration agent for queued callers with instant human escalation | `llm/agent.py` |

## Architecture

```
 Scenario replay / caller chat                    Frontend (React + Vite + TS)
              │                                   /operator   /officer   /sim
              ▼                                        ▲ REST        ▲ WebSocket
      POST /api/calls ──────────► FastAPI ─────────────┘             │
                                     │                               │
   1 Extract     Claude → claims with verbatim quotes + location mention (cached)
   2 Verify      quote grounding: verified · pending_verification · rejected
   3 Locate      MA gazetteer · old/new exits · landmarks · device location
   4 Link        H3 + time candidates → P(same) → auto · suggest · new
   5 Weigh       reliability × recency × independence → consensus, contradictions
   6 Prioritize  severity · novelty · hard overrides → queue order
   7 Dispatch    package · recommended units · agencies · suggested leads
                                     │                               │
                                     ▼                               │
              GraphStore (NetworkX) · AuditLog · EventBus ───────────┘
              LLM services: ask-next · officer briefing · corroboration agent (stretch)
```

**Design choices**

- **Deterministic core.** Claude only extracts facts and writes short text. Linking, weighting, priority and dispatch rules are pure Python functions: testable, explainable and free to run.
- **Cache-first LLM.** Extractions are cached by transcript hash, so the demo is deterministic and runs without network access once precomputed.
- **One process, one graph.** An in-memory NetworkX graph sits behind a repository class, so Neo4j or Spanner Graph can replace it without touching the pipeline.
- **Event-driven UI.** Every state change publishes one event over a WebSocket, and the frontend refetches what changed.

## Pipeline details

### 1. Extract — `pipeline/extract.py`

Claude receives the transcript and must answer through one forced tool, `record_extraction`, whose input schema is the `Extraction` contract. Temperature is 0 and the output is validated with Pydantic.

- **Claims** use a closed vocabulary. Subjects: `suspect, suspect_2, vehicle, vehicle_2, victim, scene`. Attributes: `upper_clothing_color, upper_clothing_type, lower_clothing, hair, build, height, age_range, sex, weapon, direction_of_travel, suspect_location, vehicle_make, vehicle_model, vehicle_color, vehicle_plate, vehicle_type, injury_count, victim_condition, people_count, hazard`.
- **Values** are canonical English, lowercase and short, so calls in different languages compare directly.
- **Quotes** are copied verbatim from the transcript in its original language, which is what the guard checks.
- **Location mention** captures street, cross street, town, landmark, highway route, direction, exit, `exit_is_old` and mile marker.
- **Cache:** `data/cache/extractions/<sha256(transcript)>.json`. `DEMO_MODE=cache_first` uses the cache and calls the API only on a miss; `offline` never calls the API and falls back to a minimal extraction (type `other`, no claims).
- A scenario's `caller_role_hint`, when present, overrides the extracted caller role.

### 2. Verify — `pipeline/verify.py`

Quote and transcript are normalized (Unicode casefold, punctuation stripped, whitespace collapsed, accents kept).

| Check | Status | Effect |
|---|---|---|
| Quote is an exact substring of the transcript | `verified` | Full weight |
| At least 80% of quote tokens appear in the transcript | `pending_verification` | Weight × 0.6, shown with a marker |
| Otherwise | `rejected` | Excluded from consensus, counted in guard stats |

### 3. Locate — `pipeline/locate.py`

Resolution order, first match wins:

1. **Highway:** route aliases (Pike, Mass Pike, Turnpike, 90 → I-90; 128, 95 → I-95). An exit number is looked up as a new exit first, then as an old exit (`exit_is_old` forces old). A mile marker picks the nearest entry on that route (confidence 0.7). Route plus town picks that town's entry. Kind `highway`, agency hint State Police, confidence 0.9.
2. **Landmark:** MBTA stations, campuses and named areas (confidence 0.9), with an agency hint where one applies.
3. **Intersection or street + town** from the gazetteer (confidence 0.9 for intersections, 0.8 for streets).
4. **Street without town:** if the street exists in one town, use it (0.8). If it exists in several, pick the candidate nearest the device location (0.8); with no device location, mark it `ambiguous` with confidence 0.3 and list the candidate towns.
5. **Device location** only (simulated wireless location): kind `device`, confidence 0.6. A highway route with no exit, mile or town also uses the device location, with kind `highway`.
6. Otherwise `unknown`.

### 4. Link — `pipeline/link.py`

**Candidates.** Open incidents inside the time window whose location is within radius R of the call, found with H3 (resolution 9, `grid_disk` with `k = ceil(R / 300) + 1`) and filtered by exact haversine distance. For an ambiguous location, candidates are incidents in the window whose street matches any candidate street, restricted to incidents handled by the same PSAP when any exist (a call that reached the Boston center is most likely in Boston). For an unknown location, candidates are incidents in the window with a compatible type.

**Score.**

```
geo    = 1.0 if d ≤ 0.4·R, else max(0, 1 − (d − 0.4·R) / (0.6·R))
time   = max(0, 1 − Δt_min / window_min)
type   = 1.0 same · 0.6 compatible · 0.3 vague · 0.0 incompatible
entity = mean over shared (subject, attribute) keys of: 1.0 if the call's value is among the incident's
         values, else 0.5 for a perceptual attribute and 0.0 for an identifying attribute
p_same = (0.35·geo + 0.25·time + 0.20·type + 0.20·entity) / (sum of weights of available components)
```

Identifying attributes are `sex, weapon, vehicle_make, vehicle_model, vehicle_type, vehicle_plate`; every other non-mutable attribute is perceptual, because witnesses often disagree on colors and builds but rarely on a plate or a vehicle type. `geo` is unavailable when the call has no coordinates, and `entity` is unavailable when the call and incident share no keys (mutable attributes `suspect_location` and `direction_of_travel` are excluded). Unavailable components are dropped and the remaining weights renormalized.

**Type compatibility.** Shooting, stabbing, robbery and assault are compatible with each other. Medical is compatible with those four, vehicle_crash and fire. Vehicle_crash is compatible with fire. Disturbance, suspicious_activity and other are vague (0.3) against anything. Every other pair is incompatible.

**Radius R:** highway 2000 m · intersection and landmark 400 m · street and device 600 m.

**Gates.**

- Incompatible types: `p_same` is capped at 0.49, so different emergencies are never merged.
- Location confidence below 0.5: the band is capped at `suggest`, so an unresolved location is never auto-linked.

**Bands.** `p_same ≥ 0.85` → `auto` · `0.50–0.85` → `suggest` · below 0.50 → `new` incident. Ties go to the incident handled by the same PSAP, then the most recent one. Mass-event mode raises the auto threshold to 0.90 and doubles the time window.

A `suggest` call is attached provisionally: it appears under the incident, but its claims stay out of the consensus until an operator confirms (band `confirmed`). **Split** creates a new incident from the call and recomputes both incidents.

### 5. Weigh — `pipeline/weigh.py`

```
w = role × source × recency × independence × verification
role          official 0.95 · victim 0.75 · witness 0.65 · bystander 0.50 · child 0.35 · unknown 0.50
source        first-hand 1.0 · hearsay 0.5
recency       exp(−age_min / 15) for suspect_location and direction_of_travel, else 1.0
independence  0.3 for a repeat caller (same caller_hash already in the incident), else 1.0
verification  verified 1.0 · pending_verification 0.6 · rejected excluded
```

- **Consensus** per (subject, attribute): `share(value) = Σw(value) / Σw(all values)`, with distinct source calls and first-hand sources counted. Every value is returned, never just the winner.
- **Contested** when the top share is below 0.70 and the runner-up is at least 0.20.
- **Contradictions:** the same key with different values from different calls creates `CONTRADICTS` edges, listed in the incident view.
- Role priors are carried over from v1. They are heuristic and unvalidated, and they change claim weight only, never call priority.

### 6. Prioritize — `pipeline/priority.py`

**Severity** by type: shooting 1.0 · stabbing 1.0 · fire 0.95 · medical 0.85 · robbery 0.80 · assault 0.75 · vehicle_crash 0.60 · disturbance 0.40 · suspicious_activity 0.30 · other 0.30. Flags raise the floor: `not_breathing` or `trapped` → 1.0, `weapon_present` → 0.90, `injuries_reported` → 0.85, and `child_involved` adds 0.05 (capped at 1.0). An incident takes the type and severity of its most severe non-provisional call, and its flags are the OR of those calls' flags.

**Novelty** compares the call with its linked incident (a new incident has novelty 1.0). Items are the call's non-rejected claims plus its location. An item is new if its key is absent from the incident, its value is unseen, or the call's location is farther than 0.4·R from the incident (the geo core radius, so spread-out highway callers don't all look new). `novelty = new_items / max(1, total_items)`.

```
P_dup    = p_same if band ∈ {auto, suggest, confirmed} else 0
priority = severity × (1 − P_dup × (1 − novelty))          shown as 0–100
```

**Hard overrides** set a priority floor of 0.90 and a NEW INFO badge: `new_weapon`, `new_injury`, `injury_increase`, `new_location`, `new_hazard` (fire, smoke or trapped newly reported). A new incident also shows NEW INFO with reason `new_incident`, but without the floor.

**Queue order:** priority descending, then oldest first. No call is ever removed from the queue.

### 7. Dispatch — `pipeline/dispatch.py`

- **Package:** location, type, injuries, weapons, suspects and vehicles, each with consensus share and source count; contested fields are marked.
- **Recommended units:** first matching rule in `data/dispatch_rules.json`, for example `vehicle_crash + injuries + highway → 2 EMS, 1 Fire, State Police` or `fire + trapped → 3 Engine, 1 Ladder, 2 EMS, 1 Police`. Labeled illustrative; real protocols vary by agency.
- **Agency routing:** highway → State Police; MBTA station → MBTA Transit Police; campus → campus police; otherwise the town's police, plus fire and EMS by type.
- **Suggested leads:** generated from claims on `vehicle_plate`, vehicle attributes, `direction_of_travel` and `suspect_location`, with status `suggested` until an officer accepts them.
- **Dispatch-ready:** the first time location confidence is at least 0.8 and the type is known, recorded as `dispatch_ready_at` and shown as T+ from the first call.

### Worked example (illustrative, from the demo)

| Call | Band, p_same | Novelty | Severity | Priority |
|---|---|---|---|---|
| 9th robbery caller, no new details | auto, about 0.96 | 0.0 | 0.80 | 3 |
| Caller reports the suspect pulled a knife near Newbury St | auto, about 0.9 | partial, `new_weapon` | 0.90 | 90 (floor) |
| Fire with people trapped on Westland Ave, a block away | new (type gate) | 1.0 | 1.00 | 100 |

## Knowledge graph

| Node | Key fields |
|---|---|
| Call | id, received_at, channel, language, caller_role, caller_hash, psap_id, priority, band |
| Incident | id, type, severity, status, first_seen, last_seen, dispatch_ready_at |
| Claim | id, subject, attribute, value, quote, first_hand, status, weight, provisional |
| Location | lat, lng, h3, kind, label, town, confidence, ambiguous |
| Agency | id, name, kind (local_pd, state_police, mbta_police, campus_police, fire, ems) |
| PSAP | id |
| Lead | id, description, status, assigned_unit |

| Edge | Meaning |
|---|---|
| `Call -MADE-> Claim` | Provenance of every fact |
| `Call -LINKED_TO {p_same, band, components, gates, decided_by}-> Incident` | Link decision |
| `Claim -ABOUT-> Incident` | Claim scope |
| `Claim -CONTRADICTS-> Claim` | Cross-caller conflict |
| `Incident -AT-> Location` | Resolved location |
| `Incident -ROUTED_TO-> Agency` | Routing |
| `Call -TRANSFERRED_FROM-> PSAP` | Cross-PSAP context |
| `Lead -DERIVED_FROM-> Claim` | Evidence behind a lead |

`GraphStore` wraps a `networkx.MultiDiGraph` behind a repository class (`add_call`, `add_claims`, `link`, `confirm`, `split`, lead methods), and `graph/views.py` builds the read models the API returns.

## Massachusetts specifics

| Massachusetts problem | How Nexus911 handles it | Demo |
|---|---|---|
| Same street name in many towns | Town-aware gazetteer, nearest-to-device disambiguation, "Which town?" prompt, never auto-links an ambiguous location | Washington St (Boston, Brookline, Somerville), Massachusetts Ave (Boston, Cambridge, Arlington) |
| Exits renumbered from sequential to mile-based; callers use both | Accepts old and new exit numbers, mile markers and route nicknames | I-90 Exit 63 = old Exit 8 (Palmer) |
| Calls answered by one center and transferred to another | Transfer stored as a graph edge; incident shows "Transferred from …, context preserved" | Pike scenario transfer from `palmer-local` to `msp-pike` |
| Many agencies | Routing to local PD, State Police, MBTA Transit Police, campus police, fire and EMS | `agencies.json`, `landmarks.json` |
| Multilingual callers | Quotes stay in the original language for grounding; values are canonical English, so linking works across languages | Spanish and Portuguese calls |
| Text-to-911 | `channel = text`; short texts still extract and link | Pike scenario text |
| Surge events | Mass-event mode: stricter auto-link, wider time window | Toggle on /sim |

### Demo anchor coordinates

Approximate and demo-only. Both the data files and the scenarios use exactly these values. Production would use MassGIS and MassDOT sources.

| Anchor | lat, lng |
|---|---|
| Massachusetts Ave & Boylston St, Boston | 42.3470, -71.0874 |
| Massachusetts Ave & Newbury St, Boston | 42.3485, -71.0878 |
| Hynes Convention Center station (MBTA) | 42.3480, -71.0877 |
| Symphony station (MBTA) | 42.3425, -71.0853 |
| Westland Ave, Boston | 42.3446, -71.0880 |
| Northeastern University (campus) | 42.3398, -71.0892 |
| Massachusetts Ave, Cambridge | 42.3736, -71.1190 |
| Massachusetts Ave, Arlington | 42.4154, -71.1565 |
| Washington St at Downtown Crossing, Boston | 42.3555, -71.0605 |
| Washington St at Brookline Village, Brookline | 42.3326, -71.1166 |
| Washington St at Union Square, Somerville | 42.3797, -71.0934 |
| I-90 Exit 63 (old Exit 8), Palmer, mile 63 | 42.1730, -72.3280 |
| I-90 Exit 49 (old Exit 5), Chicopee, mile 49 | 42.1600, -72.5800 |

## Data contracts

The source of truth for backend models (`backend/app/contracts.py`) and frontend types (`frontend/src/api/types.ts`).

```text
Enums
  IncidentType   shooting | stabbing | robbery | assault | medical | fire | vehicle_crash
                 | disturbance | suspicious_activity | other
  CallerRole     official | victim | witness | bystander | child | unknown
  Channel        voice | text
  Band           auto | suggest | new | confirmed
  ClaimStatus    verified | pending_verification | rejected
  LocationKind   highway | landmark | intersection | street | device | unknown
  LeadStatus     suggested | open | assigned | cleared
  OverrideReason new_weapon | new_injury | injury_increase | new_location | new_hazard | new_incident
  EventType      call.processed | incident.updated | link.changed | lead.updated
                 | settings.updated | sim.status | agent.escalated

CallIn
  transcript: str
  channel: Channel
  received_at: datetime
  caller_hash: str                       # hashed number; only for repeat-caller detection
  caller_role_hint: CallerRole | None
  device_lat: float | None
  device_lng: float | None
  psap_id: str = "boston-ecc"
  transferred_from: str | None
  scenario_id: str | None
  truth_incident: str | None             # evaluation only; never read by the pipeline
  truth_new_info: bool | None            # evaluation only

Flags
  weapon_present, injuries_reported, not_breathing, fire_or_smoke, trapped, child_involved: bool = False

LocationMention
  street, cross_street, town, landmark, highway_route, highway_direction, highway_exit: str | None
  exit_is_old: bool | None
  mile_marker: float | None
  raw: str = ""

ExtractedClaim
  subject: str; attribute: str; value: str; quote: str; first_hand: bool; confidence: float

Extraction
  language: str; incident_type: IncidentType; caller_role: CallerRole; flags: Flags
  location: LocationMention; claims: list[ExtractedClaim]; summary: str

Claim
  ExtractedClaim fields + id, call_id, incident_id, status: ClaimStatus, weight: float,
  provisional: bool, created_at: datetime

ResolvedLocation
  lat, lng: float | None; h3: str | None; kind: LocationKind; label: str; town: str | None
  confidence: float; ambiguous: bool; candidates: list[str]; agency_hint: str | None

LinkComponents
  geo, time, type, entity: float | None

LinkDecision
  call_id; incident_id; p_same: float; band: Band; components: LinkComponents
  gates: list[str]; decided_by: "system" | "operator"

QueueItem
  call_id; incident_id; received_at; priority: int (0–100); band; p_same; novelty; severity
  new_info: bool; override_reasons: list[OverrideReason]; summary; language; channel
  caller_role; location_label

ValueShare
  value: str; share: float; sources: int; first_hand_sources: int

AttributeConsensus
  subject; attribute; contested: bool; values: list[ValueShare]

IncidentSummary
  id; type; severity; status; location_label; lat; lng; call_count; first_seen; last_seen
  top_priority: int; dispatch_ready_at: datetime | None

DispatchField
  name; value; confidence: float; sources: int; contested: bool

DispatchPackage
  fields: list[DispatchField]; recommended_units: list[str]; agencies: list[str]
  rule_id: str; illustrative: bool = True

Lead
  id; incident_id; description; status: LeadStatus; assigned_unit: str | None
  source_claim_ids: list[str]

IncidentDetail
  incident: IncidentSummary; location: ResolvedLocation; calls: list[QueueItem]
  consensus: list[AttributeConsensus]; contradictions: list[{subject, attribute, values}]
  dispatch: DispatchPackage; leads: list[Lead]
  transfers: list[{call_id, from_psap, to_psap}]; timeline: list[{t, event, call_id}]

CallDetail
  call: CallIn; extraction: Extraction; claims: list[Claim]; location: ResolvedLocation
  link: LinkDecision; queue_item: QueueItem

ProcessResult
  incident_id; queue_item: QueueItem; link: LinkDecision; claims: list[Claim]

AskNext   confirm_line: str; questions: list[str]
Briefing  known: str; disputed: str; open: str

Metrics
  calls; incidents; collapse_rate: float; bands: dict[Band, int]; new_info_calls: int
  guard: {verified, pending_verification, rejected}

RuntimeSettings
  auto_link_threshold = 0.85; suggest_threshold = 0.50; time_window_min = 30
  mass_event_mode = False
  radius_m = {highway: 2000, landmark: 400, intersection: 400, street: 600, device: 600}

SimStatus
  scenario_id; running: bool; speed: float; t_offset_s: float; sim_time: datetime | None
  calls_sent: int; calls_total: int

AuditEvent
  id; ts; actor: "system" | "operator" | "officer"; action; call_id; incident_id; details: dict

DashboardEvent
  type: EventType; payload: dict; ts: datetime
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/calls` | Ingest a `CallIn`, run the pipeline, return `ProcessResult` |
| GET | `/api/queue` | All calls as `QueueItem`, ordered by priority |
| GET | `/api/calls/{id}` | `CallDetail` |
| GET | `/api/calls/{id}/explain` | `LinkDecision` with components and gates |
| GET | `/api/calls/{id}/ask-next` | `AskNext` |
| GET | `/api/incidents` | `IncidentSummary` list |
| GET | `/api/incidents/{id}` | `IncidentDetail` |
| GET | `/api/incidents/{id}/briefing` | `Briefing` |
| POST | `/api/links/{call_id}/confirm` | Operator confirms a suggested link |
| POST | `/api/links/{call_id}/split` | Operator splits a call into a new incident |
| POST | `/api/leads` | Create a lead `{incident_id, description, source_claim_ids}` |
| PATCH | `/api/leads/{id}` | Update `status` and `assigned_unit` |
| GET, PUT | `/api/settings` | `RuntimeSettings`; changes apply to new calls (use Apply & Replay) |
| GET | `/api/metrics` | `Metrics` |
| GET | `/api/audit` | `AuditEvent` list |
| POST | `/api/simulation/start` | `{scenario_id, speed}` |
| POST | `/api/simulation/stop` | Stop the replay |
| POST | `/api/reset` | Clear the graph, audit log and replay |
| WS | `/ws/dashboard` | `DashboardEvent` stream |
| POST | `/api/agent/turn` | Stretch S2: `{session_id, incident_id, caller_text}` → `{action, message, reasons}` |

## Frontend

**Flow:** Landing → Sign in (or continue as guest) → Onboarding → Console.

| Route | Screen |
|---|---|
| `/` | Landing page: the problem, how it works, the six novelties, Massachusetts specifics, limitations |
| `/signin` | Sign in with a name (kept in this browser only, no accounts) or continue as a guest. Guests get every feature |
| `/welcome` | Three-step onboarding, shown once per person; replay it from the console header |
| `/operator`, `/officer`, `/sim` | The console (`/operator` is the default) |

**Look:** the Nexus911 logo palette (black ground, one crimson `#C00000`, white type) with Fraunces, IBM Plex Sans and IBM Plex Mono, bundled with the app so the demo works offline. The rules are in [`.kiro/steering/style-guide.md`](.kiro/steering/style-guide.md); the design package (clickable mock, visual style guide, screen copy in `V2_SCREENS.md`) is in [`design/`](design/).

- **/operator:** three columns. **Queue** cards show a priority pill (crimson at 80+, yellow outline 50–79, grey below 50, always with the number), band chip, NEW INFO badge with reasons, language, channel and role chips, and T+. **Map** (Leaflet, OpenStreetMap tiles) shows incidents colored by severity and sized by call count. **Incident panel** shows the header with T+ first call and T+ dispatch-ready, transfer banner, consensus bars with every value's share and source counts, contradictions, calls with "Why linked?", Confirm and Split, the ask-next panel, and the dispatch package.
- **/officer:** incident list, three-line briefing (known, disputed, open), dispatch package, and a leads board (suggested → open → assigned → cleared).
- **/sim:** scenario picker, speed, Start, Stop and Reset, mass-event toggle, threshold sliders with Apply & Replay, and a metrics panel. Stretch: caller chat and agent panel.
- **Data flow:** `useDashboardSocket` listens on `/ws/dashboard` and triggers refetches through a small Zustand store. `VITE_USE_MOCKS=true` serves fixtures from `src/mocks/`, so the UI can be built before the backend exists. The mocks are exported from a real replay (`python scripts/export_mocks.py`) and checked against the API contracts by `backend/tests/test_frontend_mocks.py`.
- **Build and test:** `npm --prefix frontend run build` writes `frontend/dist`, which `python run.py` serves at `/` with an SPA fallback. `npm --prefix frontend test` runs the Vitest suite (pages rendered from the mocks, priority thresholds, session and route guard, sign-in validation, onboarding focus, Escape and server-down state).

## LLM usage

| Task | Model (env var) | Output | Fallback |
|---|---|---|---|
| Extraction | `CLAUDE_MODEL_EXTRACT` = `claude-sonnet-5-5` | `Extraction` via forced tool `record_extraction` | Cache, then minimal extraction |
| Ask next | `CLAUDE_MODEL_FAST` = `claude-haiku-5-5` | `AskNext` via `record_ask_next` | Rule-based templates |
| Briefing | `CLAUDE_MODEL_FAST` | `Briefing` via `record_briefing` | Template from consensus |
| Corroboration agent (stretch) | `CLAUDE_MODEL_FAST` | `{action, message, reasons}` via `record_agent_turn` | Escalate to a human |

Rules: temperature 0, structured output only through a forced tool, every output validated with Pydantic, every failure falls back without blocking the pipeline, and no LLM inside linking, weighting or priority. Ask-next questions are open-ended and never suggest an answer. Prompt texts live in `KIRO_PROMPTS.md`, Appendix A–D.

## Repository layout

```
nexus911/
├── .kiro/
│   ├── steering/              product.md · tech.md · structure.md · spec-rules.md · style-guide.md
│   └── specs/                 core-pipeline/ · api-llm-realtime/ · console-ui/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI app, routers, static frontend
│   │   ├── config.py          Settings + RuntimeSettings
│   │   ├── contracts.py       Pydantic models (source of truth)
│   │   ├── audit.py           Audit log
│   │   ├── graph/             store.py (GraphStore) · views.py (read models)
│   │   ├── pipeline/          extract · verify · locate · link · weigh · priority · dispatch · orchestrator
│   │   ├── llm/               client.py · prompts.py · agent.py (stretch)
│   │   ├── api/               routes_calls · routes_incidents · routes_links · routes_leads · routes_sim · routes_settings
│   │   ├── realtime/          bus.py (EventBus + WebSocket manager)
│   │   └── sim/               replay.py
│   ├── tests/
│   └── requirements.txt
├── design/                    design package: mock, style guide, screen copy (V2_SCREENS.md)
├── frontend/                  Vite + React + TypeScript + Tailwind + Leaflet + Zustand
│   └── src/                   api/ · mocks/ · hooks/ · components/ · pages/ · store.ts
├── data/
│   ├── ma/                    gazetteer.json · highways.json · landmarks.json · agencies.json
│   ├── dispatch_rules.json
│   ├── scenarios/             mass_ave_robbery.json · pike_crash.json · washington_st.json
│   └── cache/extractions/
├── scripts/                   precompute_extractions.py · evaluate.py
├── pytest.ini
├── Dockerfile
├── run.py
├── KIRO_PROMPTS.md
└── README.md
```

## Demo scenarios

All data is synthetic.

**1. Mass Ave robbery (Boston).** Eleven calls about an armed robbery at a convenience store near Massachusetts Ave & Boylston St. Seven callers say white jacket and three say black, but one black report is hearsay ("my neighbor said") and one is a repeat caller, so weighting gives roughly 83% white and 17% black, with black still visible. One caller speaks Spanish. At T+6 min a caller reports the suspect pulled a knife near Newbury St: NEW INFO, priority 90. At T+12 min a fire with people trapped is reported on Westland Ave, a block away: a new incident at priority 100, top of the queue.

**2. Pike crash (Palmer).** Twelve calls about a two-car crash on I-90 eastbound near Exit 63, described as "exit 63", "old exit 8", "mile marker 62", "the Turnpike" and a text-to-911 message. One caller speaks Portuguese, and one call is transferred from `palmer-local` to State Police. The SUV's color is contested (silver vs. white). At T+5 min a caller reports the SUV is now on fire: `new_hazard`. Everything collapses into one incident, and the dispatch package recommends EMS, Fire and State Police.

**3. Washington St (Boston vs. Brookline).** Fights reported on "Washington Street" from devices in Boston and Brookline become two separate incidents. A third caller with no town and no device location is attached to the Boston incident as `suggest`, and the operator is prompted to ask "Which town are you in?". A fourth Boston caller reports someone bleeding: `new_injury`.

**Three-minute demo script**

1. /sim → start "Mass Ave robbery" at 10×. Duplicates sink in the queue while the incident card fills and the white/black bars settle.
2. Click the knife call: NEW INFO badge, "Why linked?" components, ask-next prompts.
3. The fire call jumps to the top. Show the type gate in its explainer.
4. Split a call to show the human override and its audit entry.
5. /officer → briefing, dispatch package, accept a suggested lead.
6. Run "Pike crash": old and new exit numbers resolve to one incident, plus the transfer banner.
7. Run "Washington St": town ambiguity handled safely.
8. Close on the /sim metrics panel.

## Evaluation

`python scripts/evaluate.py` replays every scenario in-process with cached extractions and reports:

- **Pairwise clustering** precision, recall and F1 against `truth_incident`
- **New-incident recall:** share of ground-truth new incidents whose first call got band `new` or priority ≥ 80 (target 100%)
- **New-info escalation recall:** share of `truth_new_info` calls that received NEW INFO
- **Duplicate collapse rate:** 1 − incidents / calls
- **Guard stats:** verified, pending and rejected claims
- **Workload proxy:** calls handled as confirm-and-add (`auto`) vs. full intake

| Metric | Result |
|---|---|
| Clustering precision / recall / F1 | 1.00 / 1.00 / 1.00 |
| New-incident recall | 100% (5/5) |
| New-info escalation recall | 100% (10/10) |
| Duplicate collapse rate | 82% (28 calls → 5 incidents) |
| Claims verified / pending / rejected | 86 / 0 / 0 |
| Workload proxy: auto (confirm-and-add) / full intake | 22 / 6 |

These results come from the three synthetic demo scenarios (28 calls) written for this prototype, so they show the pipeline behaves as designed, not real-world accuracy.

Report only numbers the script actually produced.

## Run locally

```bash
git clone <repo-url> && cd nexus911
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
cp .env.example .env                                   # add ANTHROPIC_API_KEY
python scripts/precompute_extractions.py               # once; fills data/cache
python run.py                                          # http://localhost:8080 (docs at /docs)
cd frontend && npm install && npm run dev              # http://localhost:5173
pytest -q                                              # tests
python scripts/evaluate.py                             # metrics table
```

## Deploy (Cloud Run)

The graph is in memory, so run a single instance.

```bash
gcloud run deploy nexus911 --source . --region us-east1 --allow-unauthenticated \
  --max-instances 1 --timeout 3600 \
  --set-env-vars "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY,DEMO_MODE=cache_first"
```

Use Secret Manager for the API key outside a hackathon.

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Needed for live extraction, ask-next and briefing |
| `DEMO_MODE` | `cache_first` | `cache_first`: cache, then API on a miss · `offline`: never calls the API |
| `CLAUDE_MODEL_EXTRACT` | `claude-sonnet-5-5` | Extraction |
| `CLAUDE_MODEL_FAST` | `claude-haiku-5-5` | Ask-next, briefing, agent |
| `AUTO_LINK_THRESHOLD` | `0.85` | Initial runtime setting |
| `SUGGEST_THRESHOLD` | `0.50` | Initial runtime setting |
| `TIME_WINDOW_MIN` | `30` | Initial runtime setting |
| `MASS_EVENT_MODE` | `false` | Initial runtime setting |
| `PORT` | `8080` | |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |

## Safety and design principles

- **No call is dropped.** Every call stays in the queue; Nexus911 only reorders and annotates.
- **Humans decide.** Links below the auto threshold need operator confirmation, any link can be split, and every decision is audited.
- **Fail-open.** LLM or network failures never block a call; unverified facts flow through with a marker.
- **Minority accounts stay visible.** Consensus shows every value, never just the winner.
- **Credibility never lowers priority.** Role priors affect claim weight only; a child may be the only caller.
- **The agent never replaces a call-taker.** The stretch agent runs only for queued callers, asks at most three open questions, and escalates on any risk signal.
- **Synthetic data only.** No real 911 data, phone numbers or people.

## Limitations

- Prototype tested on synthetic text calls only; no real 911, CAD, NG911 or speech recognition integration.
- Weights, thresholds and role priors are heuristic and not validated with dispatch professionals.
- Cross-call subject alignment is simplified to a primary suspect and vehicle.
- Massachusetts data files are small demo samples with approximate coordinates.
- Recommended units are illustrative, not real dispatch protocols.
- State is in memory and resets on restart; latency is not benchmarked.

## Roadmap

Live voice with speech recognition and multilingual voice agents · Neo4j or Spanner Graph persistence · NG911 and CAD integration · MassGIS and MassDOT geocoding · a learned linking model trained on labeled call data · co-location and phrasing-similarity independence checks · surge forecasting · CJIS-aligned deployment.

## Built with Kiro

The build uses Kiro spec-driven development: four shared steering files in `.kiro/steering/` and one spec per teammate lane. The step-by-step prompts and credit plan are in [`KIRO_PROMPTS.md`](KIRO_PROMPTS.md).

| Lane | Owner | Kiro spec | Owns |
|---|---|---|---|
| A — Graph and scoring | `<A>` | `core-pipeline` | contracts, config, graph, locate, link, weigh, priority, dispatch, orchestrator, MA data |
| B — LLM, API and realtime | `<B>` | `api-llm-realtime` | Claude client and prompts, extract, verify, API, WebSocket, replay, scripts, scenarios |
| C — Console and demo | `<C>` | `console-ui` | Frontend, Dockerfile, deployment, demo |

## Provenance

Nexus911 v1, built for the Gemini Live Agent Challenge, prototyped one autonomous voice agent per caller with a fact-verification layer. v2 is a fresh build for `<hackathon>` with a different core: human-first operation, a claim-level knowledge graph, information-gain priority and Massachusetts-specific resolution. From v1 it keeps per-field confidence with source counts, verifying facts before trusting them, role-based credibility priors, fail-open handling and simulation replay.

## License

MIT
