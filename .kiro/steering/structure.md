---
inclusion: always
---

# Structure and lane ownership

The repository layout is in README.md, section "Repository layout".

Three teammates work in parallel lanes. Only create or edit files in your own lane unless a task explicitly says otherwise. If a change is needed in another lane, stop and describe what is needed instead of editing.

## Lane A - core-pipeline
backend/app/contracts.py, backend/app/config.py, backend/app/audit.py, backend/app/paths.py, backend/app/ids.py, backend/app/geo.py, backend/app/text.py, backend/app/reference.py, backend/app/context.py, backend/app/graph/, backend/app/flow/, backend/app/pipeline/locate.py, link.py, weigh.py, priority.py, dispatch.py, data/ma/, data/dispatch_rules.json, backend/requirements.txt, pytest.ini, and every test in backend/tests/ except test_extract.py, test_verify.py and test_api.py.

## Lane B - api-llm-realtime
backend/app/llm/, backend/app/pipeline/extract.py, verify.py, backend/app/api/, backend/app/realtime/, backend/app/sim/, backend/app/main.py, run.py, scripts/, data/scenarios/, data/cache/, backend/tests/test_extract.py, test_verify.py, test_api.py.

## Lane C - console-ui
frontend/, Dockerfile, .dockerignore.

## Interfaces between lanes
- A provides: flow.runner.process_call(call: CallIn) -> ProcessResult; confirm_link(call_id) -> ProcessResult; split_call(call_id) -> ProcessResult. graph.views: queue(), incidents(), incident_detail(id), call_detail(id), explain(call_id), metrics(), create_lead(...), update_lead(...). config.get_runtime() / update_runtime(patch). audit.AuditLog.log(...) / .events(). graph.store.GraphStore.reset().
- A also provides app.context.AppContext, the composition root that owns the single GraphStore, AuditLog, EventBus and compiled flow. The API layer resolves it through a FastAPI dependency and never imports a module-level singleton.
- B provides: pipeline.extract.extract(call: CallIn) -> Extraction; pipeline.verify.ground(extraction: Extraction, transcript: str) -> list[ClaimStatus] (one status per claim, same order).
- C uses only the HTTP and WebSocket API in README.md.
- contracts.py affects everyone: announce any change to the team before making it.

## Recorded deviations from KIRO_PROMPTS.md
- pipeline/orchestrator.py is replaced by the LangGraph layer in app/flow/ (state.py, builder.py, runner.py, nodes/). flow.runner exposes the same three entry points the playbook assigned to the orchestrator.
- Lane A gains app/context.py so the store, audit log and event bus are injected rather than imported as globals.
