# Design: core-pipeline

## Scope

The Nexus911 backend: the knowledge graph, the seven-stage call pipeline as LangGraph nodes, the LLM boundary, the HTTP and WebSocket API, and scenario replay.

This spec absorbs the playbook Lane A (core-pipeline) and Lane B (api-llm-realtime) scopes, because the build is sequential and solo rather than three teammates in parallel. Lane C (console-ui) stays a separate spec and is out of scope here.

## Source of truth

README.md is authoritative. This document does not restate it. Implement against these sections directly:

| Concern | README section |
|---|---|
| Claim extraction and closed vocabulary | 1. Extract |
| Quote grounding thresholds | 2. Verify |
| Massachusetts location resolution | 3. Locate |
| Candidate search, score, gates, bands | 4. Link |
| Claim weighting and consensus | 5. Weigh |
| Severity, novelty, priority, overrides | 6. Prioritize |
| Dispatch package and routing | 7. Dispatch |
| Node and edge shapes | Knowledge graph |
| Every model and field | Data contracts |
| Every endpoint | API |
| Expected demo outcomes | Demo scenarios |
| Evaluation metrics | Evaluation |

Prompt texts come verbatim from KIRO_PROMPTS.md Appendix A-D.

Where this design and README.md disagree, README.md wins, except for the three corrections recorded under "Design corrections" below.

## Module layout

Dependency direction is strictly downward. Nothing in a lower row imports from a higher one, which keeps the import graph acyclic.

| Layer | Modules | Rule |
|---|---|---|
| Contracts | contracts.py | Imports no other app module |
| Support | paths.py, ids.py, geo.py, text.py | No domain logic |
| Config | config.py | Process settings and runtime settings only |
| Reference | reference.py | Sole reader of data/ma and dispatch_rules.json |
| Domain | pipeline/locate, link, weigh, priority, dispatch | Pure functions, no store, no LLM, no I/O |
| LLM | llm/client.py, llm/prompts.py, pipeline/extract.py, pipeline/verify.py | Only modules that call Claude or touch the cache |
| Storage | graph/store.py, audit.py | Repository over networkx, append-only log |
| Projection | graph/views.py | Builds read models from the store |
| Orchestration | flow/ | Wires domain functions into LangGraph nodes |
| Composition | context.py | Owns the single store, audit log, event bus, compiled flow |
| Transport | api/, realtime/, sim/, main.py | Publishes events; no formulas |

Two distinct things keep distinct names: app/graph/ is the knowledge graph, app/flow/ is the LangGraph pipeline.

The domain layer never imports the storage layer. Linking and novelty take plain snapshot dataclasses, so every formula is testable without building a graph.
