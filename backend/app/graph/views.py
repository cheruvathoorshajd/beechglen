"""Read models the API returns, built from the knowledge graph.

Every read takes the application lock, so a view never observes a call that is
halfway through the commit stages. Writes from the read side (leads) are
audited as officer actions.
"""

from __future__ import annotations

import threading
from contextlib import nullcontext

from app.audit import AuditLog
from app.contracts import (
    BANDS,
    CallDetail,
    DispatchPackage,
    GuardStats,
    IncidentDetail,
    IncidentSummary,
    Lead,
    LeadStatus,
    LinkDecision,
    Metrics,
    QueueItem,
)
from app.graph.store import GraphStore, StoredIncident
from app.pipeline.priority import queue_order


class NotFoundError(KeyError):
    """Unknown call, incident or lead (HTTP 404)."""


class GraphViews:
    def __init__(self, store: GraphStore, audit: AuditLog, lock: threading.RLock | None = None) -> None:
        self._store = store
        self._audit = audit
        self._lock = lock

    def _guard(self):
        return self._lock if self._lock is not None else nullcontext()

    # -- queue and calls ----------------------------------------------------

    def queue(self) -> list[QueueItem]:
        """Every processed call, priority descending then oldest first."""
        with self._guard():
            return queue_order(call.queue_item for call in self._store.calls() if call.queue_item)

    def call_detail(self, call_id: str) -> CallDetail:
        with self._guard():
            call = self._store.get_call(call_id)
            if call is None or call.link is None or call.queue_item is None:
                raise NotFoundError(call_id)
            return CallDetail(
                call=call.payload,
                extraction=call.extraction,
                claims=self._store.claims_for_call(call_id),
                location=call.location,
                link=call.link,
                queue_item=call.queue_item,
            )

    def explain(self, call_id: str) -> LinkDecision:
        with self._guard():
            call = self._store.get_call(call_id)
            if call is None or call.link is None:
                raise NotFoundError(call_id)
            return call.link

    # -- incidents ----------------------------------------------------------

    def _summary(self, incident: StoredIncident) -> IncidentSummary:
        priorities = [
            call.queue_item.priority
            for call in self._store.calls_for_incident(incident.id)
            if call.queue_item is not None
        ]
        return IncidentSummary(
            id=incident.id,
            type=incident.type,
            severity=incident.severity,
            status="closed" if incident.status == "closed" else "open",
            location_label=incident.location.label,
            lat=incident.location.lat,
            lng=incident.location.lng,
            call_count=incident.call_count,
            first_seen=incident.first_seen,
            last_seen=incident.last_seen,
            top_priority=max(priorities, default=0),
            dispatch_ready_at=incident.dispatch_ready_at,
        )

    def incidents(self) -> list[IncidentSummary]:
        """Incidents with calls, highest priority first, then oldest."""
        with self._guard():
            summaries = [self._summary(i) for i in self._store.incidents() if i.call_count > 0]
            return sorted(summaries, key=lambda s: (-s.top_priority, s.first_seen, s.id))

    def incident_detail(self, incident_id: str) -> IncidentDetail:
        with self._guard():
            incident = self._store.get_incident(incident_id)
            if incident is None:
                raise NotFoundError(incident_id)
            calls = sorted(
                (c for c in self._store.calls_for_incident(incident_id) if c.queue_item is not None),
                key=lambda c: (c.received_at, c.id),
            )
            return IncidentDetail(
                incident=self._summary(incident),
                location=incident.location,
                calls=[call.queue_item for call in calls],
                consensus=list(incident.consensus),
                contradictions=list(incident.contradictions),
                dispatch=incident.dispatch or DispatchPackage(),
                leads=self._store.leads_for_incident(incident_id),
                transfers=self._store.transfers_for_incident(incident_id),
                timeline=sorted(incident.timeline, key=lambda entry: entry.t),
            )

    # -- metrics ------------------------------------------------------------

    def metrics(self) -> Metrics:
        with self._guard():
            calls = [call for call in self._store.calls() if call.link is not None]
            incidents = [incident for incident in self._store.incidents() if incident.call_count > 0]
            bands = {band: 0 for band in BANDS}
            for call in calls:
                bands[call.link.band] += 1
            counts = {"verified": 0, "pending_verification": 0, "rejected": 0}
            for claim in self._store.all_claims():
                counts[claim.status] += 1
            guard = GuardStats(**counts)
            return Metrics(
                calls=len(calls),
                incidents=len(incidents),
                collapse_rate=round(1 - len(incidents) / len(calls), 4) if calls else 0.0,
                bands=bands,
                new_info_calls=sum(1 for c in calls if c.queue_item is not None and c.queue_item.new_info),
                guard=guard,
            )

    # -- leads --------------------------------------------------------------

    def create_lead(self, incident_id: str, description: str, source_claim_ids: list[str]) -> Lead:
        """An officer-created lead starts ``open`` (it needs no acceptance)."""
        with self._guard():
            if self._store.get_incident(incident_id) is None:
                raise NotFoundError(incident_id)
            lead = self._store.add_lead(incident_id, description, source_claim_ids, status="open")
            self._audit.log(
                "officer",
                "lead.created",
                incident_id=incident_id,
                details={"lead_id": lead.id, "description": description},
            )
            return lead

    def update_lead(self, lead_id: str, status: LeadStatus | None, assigned_unit: str | None) -> Lead:
        with self._guard():
            previous = self._store.get_lead(lead_id)
            if previous is None:
                raise NotFoundError(lead_id)
            lead = self._store.update_lead(lead_id, status=status, assigned_unit=assigned_unit)
            self._audit.log(
                "officer",
                "lead.updated",
                incident_id=lead.incident_id,
                details={
                    "lead_id": lead_id,
                    "from_status": previous.status,
                    "to_status": lead.status,
                    "assigned_unit": lead.assigned_unit,
                },
            )
            return lead
