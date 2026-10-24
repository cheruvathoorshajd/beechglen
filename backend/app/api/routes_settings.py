"""Runtime settings, live metrics and the audit log."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import Ctx
from app.config import get_runtime, update_runtime
from app.contracts import DEFAULT_RADIUS_M, AuditEvent, Metrics, RuntimeSettings, RuntimeSettingsPatch

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings", response_model=RuntimeSettings)
def read_settings() -> RuntimeSettings:
    return get_runtime()


@router.put("/settings", response_model=RuntimeSettings)
def write_settings(body: RuntimeSettingsPatch, ctx: Ctx) -> RuntimeSettings:
    """Partial update. Changes apply to calls processed afterwards (use Apply & Replay)."""
    proposed = get_runtime().model_copy(update=body.changes())
    if proposed.suggest_threshold > proposed.auto_link_threshold:
        raise HTTPException(422, "suggest_threshold must not exceed auto_link_threshold")
    if body.radius_m is not None:
        unknown = set(body.radius_m) - set(DEFAULT_RADIUS_M)
        if unknown or any(value <= 0 for value in body.radius_m.values()):
            raise HTTPException(422, f"radius_m keys must be {sorted(DEFAULT_RADIUS_M)} with positive values")
    updated = update_runtime(body)
    ctx.bus.publish("settings.updated", updated.model_dump(mode="json"))
    return updated


@router.get("/metrics", response_model=Metrics)
def metrics(ctx: Ctx) -> Metrics:
    return ctx.views.metrics()


@router.get("/audit", response_model=list[AuditEvent])
def audit(ctx: Ctx, limit: int | None = Query(default=None, ge=1, le=5000)) -> list[AuditEvent]:
    """Every link decision and override, oldest first."""
    return ctx.audit.events(limit)
