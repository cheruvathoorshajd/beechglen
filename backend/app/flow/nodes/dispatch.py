"""Stage 7: dispatch package, agencies and suggested leads (README -> "7. Dispatch")."""

from __future__ import annotations

from app.contracts import ProcessResult
from app.flow import ops
from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState


def make_dispatch_node(deps: FlowDeps):
    def dispatch_node(state: CallFlowState) -> CallFlowState:
        call_id, incident_id = state["call_id"], state["incident_id"]
        ops.refresh_dispatch(deps, incident_id, state["call"].received_at, call_id)
        result = ProcessResult(
            incident_id=incident_id,
            queue_item=state["queue_item"],
            link=state["link"],
            claims=deps.store.claims_for_call(call_id),
        )
        return {"result": result}

    return dispatch_node
