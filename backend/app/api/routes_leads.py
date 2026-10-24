"""Officer leads: create and update (suggested -> open -> assigned -> cleared)."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import Ctx
from app.contracts import Lead, LeadCreate, LeadUpdate

router = APIRouter(prefix="/api", tags=["leads"])


@router.post("/leads", response_model=Lead, status_code=status.HTTP_201_CREATED)
def create_lead(body: LeadCreate, ctx: Ctx) -> Lead:
    lead = ctx.views.create_lead(body.incident_id, body.description, body.source_claim_ids)
    ctx.bus.publish("lead.updated", {"lead_id": lead.id, "incident_id": lead.incident_id, "status": lead.status})
    return lead


@router.patch("/leads/{lead_id}", response_model=Lead)
def update_lead(lead_id: str, body: LeadUpdate, ctx: Ctx) -> Lead:
    lead = ctx.views.update_lead(lead_id, body.status, body.assigned_unit)
    ctx.bus.publish("lead.updated", {"lead_id": lead.id, "incident_id": lead.incident_id, "status": lead.status})
    return lead
