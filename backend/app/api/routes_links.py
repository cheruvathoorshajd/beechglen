"""Operator overrides: confirm or split a link. Both are audited."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import Ctx
from app.contracts import ProcessResult

router = APIRouter(prefix="/api", tags=["links"])


@router.post("/links/{call_id}/confirm", response_model=ProcessResult)
def confirm_link(call_id: str, ctx: Ctx) -> ProcessResult:
    """Operator confirms a suggested link; its claims join the consensus."""
    ctx.views.explain(call_id)  # 404 for an unknown call
    result = ctx.runner.confirm_link(call_id)
    ctx.bus.publish(
        "link.changed",
        {"action": "confirm", "call_id": call_id, "incident_id": result.incident_id, "band": result.link.band},
    )
    return result


@router.post("/links/{call_id}/split", response_model=ProcessResult)
def split_call(call_id: str, ctx: Ctx) -> ProcessResult:
    """Operator splits a call into a new incident; both incidents recompute."""
    previous = ctx.views.explain(call_id).incident_id
    result = ctx.runner.split_call(call_id)
    ctx.bus.publish(
        "link.changed",
        {
            "action": "split",
            "call_id": call_id,
            "incident_id": result.incident_id,
            "previous_incident_id": previous,
            "band": result.link.band,
        },
    )
    return result
