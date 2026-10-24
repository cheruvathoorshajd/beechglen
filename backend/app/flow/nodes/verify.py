"""Stage 2: quote grounding (README -> "2. Verify")."""

from __future__ import annotations

import logging

from app.contracts import ClaimStatus
from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState

logger = logging.getLogger(__name__)


def make_verify_node(deps: FlowDeps):
    def verify_node(state: CallFlowState) -> CallFlowState:
        extraction = state["extraction"]
        count = len(extraction.claims)
        try:
            statuses: list[ClaimStatus] = list(deps.ground(extraction, state["call"].transcript))
        except Exception:  # noqa: BLE001 - fail-open: unverified facts flow through with a marker
            logger.exception("Quote grounding failed; marking claims pending")
            statuses = []
        if len(statuses) != count:
            statuses = (statuses + ["pending_verification"] * count)[:count]
        return {"statuses": statuses}

    return verify_node
