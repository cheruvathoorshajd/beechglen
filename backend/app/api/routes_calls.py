"""Call intake, the priority queue, call detail, link explanations and ask-next."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import Ctx
from app.contracts import AskNext, CallDetail, CallIn, LinkDecision, ProcessResult, QueueItem
from app.realtime.bus import call_processed_payload

router = APIRouter(prefix="/api", tags=["calls"])


@router.post("/calls", response_model=ProcessResult)
def ingest_call(call: CallIn, ctx: Ctx) -> ProcessResult:
    """Run one call through the pipeline. The call is never dropped."""
    result = ctx.runner.process_call(call)
    ctx.bus.publish("call.processed", call_processed_payload(result))
    return result


@router.get("/queue", response_model=list[QueueItem])
def queue(ctx: Ctx) -> list[QueueItem]:
    """Every call, priority descending then oldest first."""
    return ctx.views.queue()


@router.get("/calls/{call_id}", response_model=CallDetail)
def call_detail(call_id: str, ctx: Ctx) -> CallDetail:
    return ctx.views.call_detail(call_id)


@router.get("/calls/{call_id}/explain", response_model=LinkDecision)
def explain(call_id: str, ctx: Ctx) -> LinkDecision:
    """The link decision with every score component and gate."""
    return ctx.views.explain(call_id)


@router.get("/calls/{call_id}/ask-next", response_model=AskNext)
def ask_next(call_id: str, ctx: Ctx) -> AskNext:
    """A confirm line plus 2-3 open questions for the call-taker."""
    detail = ctx.views.call_detail(call_id)
    incident = ctx.views.incident_detail(detail.link.incident_id)
    return ctx.assist.ask_next(detail, incident)
