"""The claim-weighted knowledge graph.

A single ``networkx.MultiDiGraph`` behind a repository class. Callers never see
the graph itself, only the methods on :class:`GraphStore`, so swapping in Neo4j
or Spanner Graph later touches this file and nothing else.

Node and edge shapes follow README -> "Knowledge graph".

Internal mutable state lives in the ``Stored*`` dataclasses. Projection to the
API contracts happens in :mod:`app.graph.views`, which keeps storage concerns
out of the read models.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Iterable

import networkx as nx

from app.contracts import (
    CallIn,
    Claim,
    Contradiction,
    DispatchPackage,
    Extraction,
    Flags,
    IncidentType,
    Lead,
    LeadStatus,
    LinkDecision,
    QueueItem,
    ResolvedLocation,
    TimelineEntry,
    TransferRecord,
)
from app.ids import next_id, reset_ids


class NodeKind(StrEnum):
    """Node labels in the knowledge graph."""

    CALL = "Call"
    INCIDENT = "Incident"
    CLAIM = "Claim"
    LOCATION = "Location"
    AGENCY = "Agency"
    PSAP = "PSAP"
    LEAD = "Lead"


class RelKind(StrEnum):
    """Edge labels in the knowledge graph."""

    MADE = "MADE"
    LINKED_TO = "LINKED_TO"
    ABOUT = "ABOUT"
    CONTRADICTS = "CONTRADICTS"
    AT = "AT"
    ROUTED_TO = "ROUTED_TO"
    TRANSFERRED_FROM = "TRANSFERRED_FROM"
    DERIVED_FROM = "DERIVED_FROM"


# ---------------------------------------------------------------------------
# Internal records
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class StoredCall:
    """Mutable per-call state held on a ``Call`` node."""

    id: str
    payload: CallIn
    extraction: Extraction
    location: ResolvedLocation
    claim_ids: list[str] = field(default_factory=list)
    link: LinkDecision | None = None
    queue_item: QueueItem | None = None
    severity: float = 0.0

    @property
    def received_at(self) -> datetime:
        return self.payload.received_at

    @property
    def caller_hash(self) -> str:
        return self.payload.caller_hash

    @property
    def psap_id(self) -> str:
        return self.payload.psap_id

    @property
    def flags(self) -> Flags:
        return self.extraction.flags

    def is_provisional(self) -> bool:
        return self.link is not None and self.link.is_provisional()


@dataclass(slots=True)
class StoredIncident:
    """Mutable per-incident state held on an ``Incident`` node."""

    id: str
    type: IncidentType
    severity: float
    first_seen: datetime
    last_seen: datetime
    location: ResolvedLocation
    flags: Flags = field(default_factory=Flags)
    status: str = "open"
    call_ids: list[str] = field(default_factory=list)
    agency_ids: list[str] = field(default_factory=list)
    dispatch: DispatchPackage | None = None
    dispatch_ready_at: datetime | None = None
    timeline: list[TimelineEntry] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)

    @property
    def call_count(self) -> int:
        return len(self.call_ids)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class GraphStore:
    """Repository over the in-memory knowledge graph.

    Every public method takes the lock, so the store is safe to use from the
    request path and the replay task at the same time.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._graph = nx.MultiDiGraph()
        self._calls: dict[str, StoredCall] = {}
        self._incidents: dict[str, StoredIncident] = {}
        self._claims: dict[str, Claim] = {}
        self._leads: dict[str, Lead] = {}
        self._transfers: list[TransferRecord] = []

    # -- lifecycle ----------------------------------------------------------

    def reset(self) -> None:
        """Drop all state and restart identifier counters."""
        with self._lock:
            self._graph.clear()
            self._calls.clear()
            self._incidents.clear()
            self._claims.clear()
            self._leads.clear()
            self._transfers.clear()
            reset_ids()

    # -- calls --------------------------------------------------------------

    def add_call(
        self,
        payload: CallIn,
        extraction: Extraction,
        location: ResolvedLocation,
    ) -> StoredCall:
        """Insert a ``Call`` node (plus its PSAP transfer edge) and return it."""
        with self._lock:
            call_id = next_id("call")
            stored = StoredCall(
                id=call_id, payload=payload, extraction=extraction, location=location
            )
            self._graph.add_node(call_id, kind=NodeKind.CALL, record=stored)
            self._calls[call_id] = stored

            self._ensure_psap(payload.psap_id)
            if payload.transferred_from:
                origin = self._ensure_psap(payload.transferred_from)
                self._graph.add_edge(call_id, origin, key=RelKind.TRANSFERRED_FROM)
                self._transfers.append(
                    TransferRecord(
                        call_id=call_id,
                        from_psap=payload.transferred_from,
                        to_psap=payload.psap_id,
                    )
                )
            return stored

    def get_call(self, call_id: str) -> StoredCall | None:
        with self._lock:
            return self._calls.get(call_id)

    def require_call(self, call_id: str) -> StoredCall:
        call = self.get_call(call_id)
        if call is None:
            raise KeyError(f"Unknown call: {call_id}")
        return call

    def calls(self) -> list[StoredCall]:
        with self._lock:
            return list(self._calls.values())

    def call_count(self) -> int:
        with self._lock:
            return len(self._calls)

    # -- claims -------------------------------------------------------------

    def add_claims(self, call_id: str, claims: Iterable[Claim]) -> list[Claim]:
        """Attach claims to a call, wiring ``MADE`` and ``ABOUT`` edges."""
        with self._lock:
            call = self.require_call(call_id)
            stored: list[Claim] = []
            for claim in claims:
                self._graph.add_node(claim.id, kind=NodeKind.CLAIM, record=claim)
                self._graph.add_edge(call_id, claim.id, key=RelKind.MADE)
                if claim.incident_id:
                    self._graph.add_edge(claim.id, claim.incident_id, key=RelKind.ABOUT)
                self._claims[claim.id] = claim
                call.claim_ids.append(claim.id)
                stored.append(claim)
            return stored

    def get_claim(self, claim_id: str) -> Claim | None:
        with self._lock:
            return self._claims.get(claim_id)

    def claims_for_call(self, call_id: str) -> list[Claim]:
        with self._lock:
            call = self._calls.get(call_id)
            if call is None:
                return []
            return [self._claims[cid] for cid in call.claim_ids if cid in self._claims]

    def claims_for_incident(self, incident_id: str, *, include_provisional: bool = False) -> list[Claim]:
        """Claims scoped to an incident, provisional ones excluded by default."""
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                return []
            result: list[Claim] = []
            for call_id in incident.call_ids:
                for claim in self.claims_for_call(call_id):
                    if claim.status == "rejected":
                        continue
                    if claim.provisional and not include_provisional:
                        continue
                    result.append(claim)
            return result

    def all_claims(self) -> list[Claim]:
        with self._lock:
            return list(self._claims.values())

    def replace_claim(self, claim: Claim) -> None:
        """Overwrite a stored claim (used when weights or status change)."""
        with self._lock:
            if claim.id not in self._claims:
                raise KeyError(f"Unknown claim: {claim.id}")
            self._claims[claim.id] = claim
            self._graph.nodes[claim.id]["record"] = claim

    def set_claim_incident(self, claim_id: str, incident_id: str) -> None:
        with self._lock:
            claim = self._claims[claim_id]
            updated = claim.model_copy(update={"incident_id": incident_id})
            self._claims[claim_id] = updated
            self._graph.nodes[claim_id]["record"] = updated
            self._graph.add_edge(claim_id, incident_id, key=RelKind.ABOUT)

    def set_claim_provisional(self, claim_id: str, provisional: bool) -> None:
        with self._lock:
            claim = self._claims[claim_id]
            updated = claim.model_copy(update={"provisional": provisional})
            self._claims[claim_id] = updated
            self._graph.nodes[claim_id]["record"] = updated

    def add_contradiction(self, claim_a: str, claim_b: str) -> None:
        with self._lock:
            self._graph.add_edge(claim_a, claim_b, key=RelKind.CONTRADICTS)

    def contradiction_pairs(self) -> list[tuple[str, str]]:
        with self._lock:
            return [
                (u, v)
                for u, v, key in self._graph.edges(keys=True)
                if key == RelKind.CONTRADICTS
            ]

    # -- incidents ----------------------------------------------------------

    def create_incident(
        self,
        *,
        incident_type: IncidentType,
        severity: float,
        location: ResolvedLocation,
        flags: Flags,
        at: datetime,
    ) -> StoredIncident:
        """Insert an ``Incident`` node and its ``AT`` location edge."""
        with self._lock:
            incident_id = next_id("incident")
            incident = StoredIncident(
                id=incident_id,
                type=incident_type,
                severity=severity,
                first_seen=at,
                last_seen=at,
                location=location,
                flags=flags,
            )
            self._graph.add_node(incident_id, kind=NodeKind.INCIDENT, record=incident)
            self._incidents[incident_id] = incident
            self._attach_location(incident_id, location)
            return incident

    def get_incident(self, incident_id: str) -> StoredIncident | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def require_incident(self, incident_id: str) -> StoredIncident:
        incident = self.get_incident(incident_id)
        if incident is None:
            raise KeyError(f"Unknown incident: {incident_id}")
        return incident

    def incidents(self) -> list[StoredIncident]:
        with self._lock:
            return list(self._incidents.values())

    def incident_count(self) -> int:
        with self._lock:
            return len(self._incidents)

    def open_incidents_within(self, moment: datetime, window_min: int) -> list[StoredIncident]:
        """Open incidents whose last activity is inside the time window.

        Candidate generation for linking; the geometric filter happens in
        :mod:`app.pipeline.link`.
        """
        window = timedelta(minutes=window_min)
        with self._lock:
            return [
                incident
                for incident in self._incidents.values()
                if incident.status == "open" and abs(moment - incident.last_seen) <= window
            ]

    def update_incident_location(self, incident_id: str, location: ResolvedLocation) -> None:
        with self._lock:
            incident = self.require_incident(incident_id)
            incident.location = location
            self._attach_location(incident_id, location)

    def touch_incident(
        self,
        incident_id: str,
        *,
        at: datetime,
        incident_type: IncidentType | None = None,
        severity: float | None = None,
        flags: Flags | None = None,
    ) -> StoredIncident:
        """Roll a call's contribution up into the incident header."""
        with self._lock:
            incident = self.require_incident(incident_id)
            incident.last_seen = max(incident.last_seen, at)
            incident.first_seen = min(incident.first_seen, at)
            if severity is not None and severity > incident.severity:
                incident.severity = severity
                if incident_type is not None:
                    incident.type = incident_type
            if flags is not None:
                incident.flags = incident.flags.merged_with(flags)
            return incident

    def set_incident_header(
        self,
        incident_id: str,
        *,
        incident_type: IncidentType,
        severity: float,
        flags: Flags,
    ) -> None:
        """Replace the rolled-up header outright (used after a split)."""
        with self._lock:
            incident = self.require_incident(incident_id)
            incident.type = incident_type
            incident.severity = severity
            incident.flags = flags

    def set_dispatch(
        self,
        incident_id: str,
        package: DispatchPackage,
        *,
        ready_at: datetime | None = None,
    ) -> None:
        with self._lock:
            incident = self.require_incident(incident_id)
            incident.dispatch = package
            if ready_at is not None and incident.dispatch_ready_at is None:
                incident.dispatch_ready_at = ready_at
            for agency in package.agencies:
                self.route_to_agency(incident_id, agency)

    def set_contradictions(self, incident_id: str, contradictions: list[Contradiction]) -> None:
        with self._lock:
            self.require_incident(incident_id).contradictions = list(contradictions)

    def append_timeline(self, incident_id: str, entry: TimelineEntry) -> None:
        with self._lock:
            self.require_incident(incident_id).timeline.append(entry)

    def route_to_agency(self, incident_id: str, agency_name: str) -> None:
        with self._lock:
            node = f"agency:{agency_name}"
            if node not in self._graph:
                self._graph.add_node(node, kind=NodeKind.AGENCY, name=agency_name)
            self._graph.add_edge(incident_id, node, key=RelKind.ROUTED_TO)
            incident = self.require_incident(incident_id)
            if agency_name not in incident.agency_ids:
                incident.agency_ids.append(agency_name)

    # -- linking ------------------------------------------------------------

    def attach(self, call_id: str, decision: LinkDecision) -> None:
        """Record a link decision and add the call to its incident."""
        with self._lock:
            call = self.require_call(call_id)
            incident = self.require_incident(decision.incident_id)

            if call.link is not None and call.link.incident_id != decision.incident_id:
                self.detach(call_id)

            call.link = decision
            self._graph.add_edge(
                call_id,
                decision.incident_id,
                key=RelKind.LINKED_TO,
                p_same=decision.p_same,
                band=decision.band,
                components=decision.components.model_dump(),
                gates=list(decision.gates),
                decided_by=decision.decided_by,
            )
            if call_id not in incident.call_ids:
                incident.call_ids.append(call_id)

            provisional = decision.is_provisional()
            for claim_id in call.claim_ids:
                self.set_claim_incident(claim_id, decision.incident_id)
                self.set_claim_provisional(claim_id, provisional)

    def detach(self, call_id: str) -> str | None:
        """Remove a call from its current incident. Returns the old incident id."""
        with self._lock:
            call = self.require_call(call_id)
            if call.link is None:
                return None
            old_id = call.link.incident_id
            incident = self._incidents.get(old_id)
            if incident and call_id in incident.call_ids:
                incident.call_ids.remove(call_id)
            if self._graph.has_edge(call_id, old_id, key=RelKind.LINKED_TO):
                self._graph.remove_edge(call_id, old_id, key=RelKind.LINKED_TO)
            for claim_id in call.claim_ids:
                if self._graph.has_edge(claim_id, old_id, key=RelKind.ABOUT):
                    self._graph.remove_edge(claim_id, old_id, key=RelKind.ABOUT)
            call.link = None
            return old_id

    def link_edge_data(self, call_id: str, incident_id: str) -> dict | None:
        with self._lock:
            if not self._graph.has_edge(call_id, incident_id, key=RelKind.LINKED_TO):
                return None
            return dict(self._graph.edges[call_id, incident_id, RelKind.LINKED_TO])

    def set_queue_item(self, call_id: str, item: QueueItem) -> None:
        with self._lock:
            self.require_call(call_id).queue_item = item

    def set_call_severity(self, call_id: str, severity: float) -> None:
        with self._lock:
            self.require_call(call_id).severity = severity

    def calls_for_incident(self, incident_id: str) -> list[StoredCall]:
        with self._lock:
            incident = self._incidents.get(incident_id)
            if incident is None:
                return []
            return [self._calls[cid] for cid in incident.call_ids if cid in self._calls]

    def has_caller(self, incident_id: str, caller_hash: str, *, exclude_call: str | None = None) -> bool:
        """True when this caller already contributed to the incident."""
        for call in self.calls_for_incident(incident_id):
            if call.id == exclude_call:
                continue
            if call.caller_hash == caller_hash:
                return True
        return False

    def transfers_for_incident(self, incident_id: str) -> list[TransferRecord]:
        call_ids = {call.id for call in self.calls_for_incident(incident_id)}
        with self._lock:
            return [record for record in self._transfers if record.call_id in call_ids]

    # -- leads --------------------------------------------------------------

    def add_lead(
        self,
        incident_id: str,
        description: str,
        source_claim_ids: list[str] | None = None,
        status: LeadStatus = "suggested",
    ) -> Lead:
        with self._lock:
            self.require_incident(incident_id)
            lead = Lead(
                id=next_id("lead"),
                incident_id=incident_id,
                description=description,
                status=status,
                source_claim_ids=list(source_claim_ids or []),
            )
            self._graph.add_node(lead.id, kind=NodeKind.LEAD, record=lead)
            for claim_id in lead.source_claim_ids:
                if claim_id in self._claims:
                    self._graph.add_edge(lead.id, claim_id, key=RelKind.DERIVED_FROM)
            self._leads[lead.id] = lead
            return lead

    def update_lead(
        self,
        lead_id: str,
        *,
        status: LeadStatus | None = None,
        assigned_unit: str | None = None,
    ) -> Lead:
        with self._lock:
            lead = self._leads.get(lead_id)
            if lead is None:
                raise KeyError(f"Unknown lead: {lead_id}")
            changes: dict[str, object] = {}
            if status is not None:
                changes["status"] = status
            if assigned_unit is not None:
                changes["assigned_unit"] = assigned_unit
            updated = lead.model_copy(update=changes)
            self._leads[lead_id] = updated
            self._graph.nodes[lead_id]["record"] = updated
            return updated

    def leads_for_incident(self, incident_id: str) -> list[Lead]:
        with self._lock:
            return [lead for lead in self._leads.values() if lead.incident_id == incident_id]

    def lead_descriptions(self, incident_id: str) -> set[str]:
        """Existing descriptions, so suggested leads are not duplicated."""
        return {lead.description for lead in self.leads_for_incident(incident_id)}

    # -- introspection ------------------------------------------------------

    def node_counts(self) -> dict[str, int]:
        """Node totals by label. Useful for debugging and tests."""
        counts: dict[str, int] = {}
        with self._lock:
            for _, data in self._graph.nodes(data=True):
                kind = str(data.get("kind", "Unknown"))
                counts[kind] = counts.get(kind, 0) + 1
        return counts

    def edge_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        with self._lock:
            for _, _, key in self._graph.edges(keys=True):
                counts[str(key)] = counts.get(str(key), 0) + 1
        return counts

    # -- internals ----------------------------------------------------------

    def _ensure_psap(self, psap_id: str) -> str:
        node = f"psap:{psap_id}"
        if node not in self._graph:
            self._graph.add_node(node, kind=NodeKind.PSAP, psap_id=psap_id)
        return node

    def _attach_location(self, incident_id: str, location: ResolvedLocation) -> None:
        node = f"loc:{incident_id}"
        self._graph.add_node(node, kind=NodeKind.LOCATION, record=location)
        self._graph.add_edge(incident_id, node, key=RelKind.AT)
