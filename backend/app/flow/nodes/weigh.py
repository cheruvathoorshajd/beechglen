"""Stage 5: claim weights, consensus and contradictions (README -> "5. Weigh")."""

from __future__ import annotations

from app.flow import ops
from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState


def make_weigh_node(deps: FlowDeps):
    def weigh_node(state: CallFlowState) -> CallFlowState:
        ops.reweigh(deps, state["incident_id"])
        return {"claims": deps.store.claims_for_call(state["call_id"])}

    return weigh_node
