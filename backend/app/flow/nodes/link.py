"""Stage 4: link the call to an incident or open a new one (README -> "4. Link").

The incident is snapshotted before the call is written, because novelty must
compare the call with the incident as it was beforehand.
"""

from __future__ import annotations

from app.contracts import Claim, LinkDecision
from app.flow import ops
from app.flow.deps import FlowDeps
from app.flow.state import CallFlowState
from app.ids import next_id
from app.pipeline import link as linking
from app.pipeline.priority import severity


def make_link_node(deps: FlowDeps):
    def link_node(state: CallFlowState) -> CallFlowState:
        store = deps.store
        reference = deps.reference()
        settings = deps.runtime()
        call, extraction = state["call"], state["extraction"]
        statuses, location = state["statuses"], state["location"]

        features = ops.call_features(call, extraction, statuses, location, reference)
        open_incidents = store.open_incidents_within(call.received_at, settings.effective_window_min())
        candidates = [ops.incident_candidate(store, incident, reference) for incident in open_incidents]
        outcome = linking.decide(features, candidates, settings)

        snapshot = None
        if not outcome.creates_incident():
            snapshot = ops.incident_snapshot(store, store.require_incident(outcome.incident_id))

        stored = store.add_call(call, extraction, location)
        claims = [
            Claim(
                id=next_id("claim"),
                call_id=stored.id,
                subject=item.subject,
                attribute=item.attribute,
                value=item.value,
                quote=item.quote,
                first_hand=item.first_hand,
                confidence=item.confidence,
                status=status,
                created_at=call.received_at,
            )
            for item, status in zip(extraction.claims, statuses)
        ]
        store.add_claims(stored.id, claims)

        if outcome.creates_incident():
            incident_id = store.create_incident(
                incident_type=extraction.incident_type,
                severity=severity(extraction.incident_type, extraction.flags),
                location=location,
                flags=extraction.flags,
                at=call.received_at,
            ).id
        else:
            incident_id = outcome.incident_id

        decision = LinkDecision(
            call_id=stored.id,
            incident_id=incident_id,
            p_same=outcome.p_same,
            band=outcome.band,
            components=outcome.components,
            gates=list(outcome.gates),
            decided_by="system",
        )
        store.attach(stored.id, decision)
        ops.refresh_header(deps, incident_id)

        deps.audit.log(
            "system",
            "link.decided",
            call_id=stored.id,
            incident_id=incident_id,
            details={
                "band": decision.band,
                "p_same": decision.p_same,
                "components": decision.components.model_dump(),
                "gates": decision.gates,
                "candidates_considered": outcome.considered,
                "distance_m": None if outcome.distance_m is None else round(outcome.distance_m, 1),
            },
        )
        return {
            "call_id": stored.id,
            "incident_id": incident_id,
            "created_incident": outcome.creates_incident(),
            "link": decision,
            "snapshot": snapshot,
        }

    return link_node
