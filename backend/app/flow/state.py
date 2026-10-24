"""State carried through the LangGraph call pipeline."""

from __future__ import annotations

from typing import TypedDict

from app.contracts import (
    CallIn,
    Claim,
    ClaimStatus,
    Extraction,
    LinkDecision,
    ProcessResult,
    QueueItem,
    ResolvedLocation,
)
from app.pipeline.priority import IncidentSnapshot


class CallFlowState(TypedDict, total=False):
    """Partial state: each node returns only the keys it produces."""

    call: CallIn
    extraction: Extraction
    statuses: list[ClaimStatus]
    location: ResolvedLocation
    call_id: str
    incident_id: str
    created_incident: bool
    link: LinkDecision
    snapshot: IncidentSnapshot | None
    claims: list[Claim]
    queue_item: QueueItem
    result: ProcessResult
