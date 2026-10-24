"""Stage 1: extract claims (README -> "1. Extract")."""

from __future__ import annotations

import logging

from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState
from app.pipeline.extract import apply_role_hint, minimal_extraction

logger = logging.getLogger(__name__)


def make_extract_node(deps: FlowDeps):
    def extract_node(state: CallFlowState) -> CallFlowState:
        call = state["call"]
        try:
            extraction = deps.extract(call)
        except Exception:  # noqa: BLE001 - fail-open: the call must enter the graph
            logger.exception("Extraction failed; using the minimal extraction")
            extraction = apply_role_hint(minimal_extraction(call), call)
        return {"extraction": extraction}

    return extract_node
