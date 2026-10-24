"""Scenario replay control and reset."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import Ctx
from app.contracts import SimStartRequest, SimStatus

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulation/start", response_model=SimStatus)
def start_simulation(body: SimStartRequest, ctx: Ctx) -> SimStatus:
    """Replay ``data/scenarios/<scenario_id>.json`` at ``speed``x (stops any running replay)."""
    return ctx.replay.start(body.scenario_id, body.speed)


@router.post("/simulation/stop", response_model=SimStatus)
def stop_simulation(ctx: Ctx) -> SimStatus:
    return ctx.replay.stop()


@router.post("/reset", response_model=SimStatus)
def reset(ctx: Ctx) -> SimStatus:
    """Clear the graph, the audit log and the replay. Runtime settings are kept."""
    ctx.reset()
    sim_status = ctx.replay.status()
    ctx.bus.publish("sim.status", sim_status.model_dump(mode="json"))
    ctx.bus.publish("incident.updated", {"reset": True})
    return sim_status
