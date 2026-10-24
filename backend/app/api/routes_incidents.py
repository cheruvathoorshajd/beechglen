"""Incident list, incident detail and the officer briefing."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import Ctx
from app.contracts import Briefing, IncidentDetail, IncidentSummary

router = APIRouter(prefix="/api", tags=["incidents"])


@router.get("/incidents", response_model=list[IncidentSummary])
def incidents(ctx: Ctx) -> list[IncidentSummary]:
    return ctx.views.incidents()


@router.get("/incidents/{incident_id}", response_model=IncidentDetail)
def incident_detail(incident_id: str, ctx: Ctx) -> IncidentDetail:
    return ctx.views.incident_detail(incident_id)


@router.get("/incidents/{incident_id}/briefing", response_model=Briefing)
def briefing(incident_id: str, ctx: Ctx) -> Briefing:
    """Three lines for responding officers: known, disputed, open."""
    return ctx.assist.briefing(ctx.views.incident_detail(incident_id))
