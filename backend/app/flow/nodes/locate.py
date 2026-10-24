"""Stage 3: Massachusetts location resolution (README -> "3. Locate")."""

from __future__ import annotations

from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState
from app.pipeline.locate import resolve


def make_locate_node(deps: FlowDeps):
    def locate_node(state: CallFlowState) -> CallFlowState:
        call = state["call"]
        location = resolve(state["extraction"].location, call.device_coords(), deps.reference())
        return {"location": location}

    return locate_node
