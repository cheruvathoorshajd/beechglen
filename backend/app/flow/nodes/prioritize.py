"""Stage 6: severity, novelty, priority and hard overrides (README -> "6. Prioritize")."""

from __future__ import annotations

from app.contracts import OverrideReason, QueueItem
from app.flow import ops
from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState
from app.pipeline import priority as prio


def make_prioritize_node(deps: FlowDeps):
    def prioritize_node(state: CallFlowState) -> CallFlowState:
        store = deps.store
        settings = deps.runtime()
        call, extraction, location = state["call"], state["extraction"], state["location"]
        call_id, incident_id, decision = state["call_id"], state["incident_id"], state["link"]

        call_severity = prio.severity(extraction.incident_type, extraction.flags)
        store.set_call_severity(call_id, call_severity)

        snapshot = state.get("snapshot")
        reasons: list[OverrideReason]
        if state.get("created_incident") or snapshot is None:
            novelty, reasons = 1.0, ["new_incident"]
        else:
            radius = settings.radius_for(location.kind)
            triples = ops.grounded_triples(extraction, state["statuses"])
            novelty = prio.novelty(triples, location, snapshot, radius)
            reasons = prio.override_reasons(triples, extraction.flags, location, snapshot, radius)

        value = prio.priority(call_severity, decision.band, decision.p_same, novelty, reasons)
        item = QueueItem(
            call_id=call_id,
            incident_id=incident_id,
            received_at=call.received_at,
            priority=prio.to_display(value),
            band=decision.band,
            p_same=decision.p_same,
            novelty=novelty,
            severity=call_severity,
            new_info=bool(reasons),
            override_reasons=reasons,
            summary=extraction.summary,
            language=extraction.language,
            channel=call.channel,
            caller_role=extraction.caller_role,
            location_label=location.label,
        )
        store.set_queue_item(call_id, item)

        if state.get("created_incident"):
            ops.add_timeline(store, incident_id, call.received_at, f"New incident ({extraction.incident_type})", call_id)
        else:
            ops.add_timeline(
                store, incident_id, call.received_at, f"Linked ({decision.band}, p={decision.p_same:.2f})", call_id
            )
        overrides = [reason for reason in reasons if reason != "new_incident"]
        if overrides:
            ops.add_timeline(store, incident_id, call.received_at, "NEW INFO: " + ", ".join(overrides), call_id)
            deps.audit.log(
                "system",
                "priority.override",
                call_id=call_id,
                incident_id=incident_id,
                details={"reasons": overrides, "priority": item.priority, "novelty": novelty},
            )
        return {"queue_item": item}

    return prioritize_node
