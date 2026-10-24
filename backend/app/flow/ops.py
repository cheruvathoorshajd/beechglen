"""Store <-> pipeline glue shared by the nodes and the runner.

These helpers read the store, build the plain snapshots the pure pipeline
functions take, and write results back. They hold no formulas.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
from functools import reduce

from app.contracts import (
    CallIn,
    ClaimStatus,
    Extraction,
    Flags,
    LocationMention,
    ResolvedLocation,
    TimelineEntry,
)
from app.flow.deps import FlowDeps
from app.graph.store import GraphStore, StoredCall, StoredIncident
from app.pipeline import dispatch as dispatch_rules
from app.pipeline import priority as prio
from app.pipeline import weigh
from app.pipeline.link import CallFeatures, IncidentCandidate
from app.reference import ReferenceData

ClaimKey = tuple[str, str]


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def as_aware(moment: datetime) -> datetime:
    """Treat naive timestamps as UTC so every comparison is well defined."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def normalize_call(call: CallIn) -> CallIn:
    if call.received_at.tzinfo is not None:
        return call
    return call.model_copy(update={"received_at": as_aware(call.received_at)})


def sim_now(store: GraphStore) -> datetime:
    """The simulated clock: latest call time seen, else wall-clock UTC."""
    calls = store.calls()
    if not calls:
        return datetime.now(timezone.utc)
    return max(call.received_at for call in calls)


def values_by_key(triples: Iterable[tuple[str, str, str]]) -> dict[ClaimKey, frozenset[str]]:
    grouped: dict[ClaimKey, set[str]] = {}
    for subject, attribute, value in triples:
        grouped.setdefault((subject, attribute), set()).add(value)
    return {key: frozenset(values) for key, values in grouped.items()}


def mention_streets(mention: LocationMention, reference: ReferenceData) -> frozenset[str]:
    """Canonical street names a caller mentioned (for ambiguous-location search)."""
    names = {
        reference.gazetteer.canonical_street(mention.street),
        reference.gazetteer.canonical_street(mention.cross_street),
    }
    return frozenset(name for name in names if name)


def merged_flags(flags: Iterable[Flags]) -> Flags:
    return reduce(lambda acc, item: acc.merged_with(item), flags, Flags())


def call_severity(call: StoredCall) -> float:
    return prio.severity(call.extraction.incident_type, call.extraction.flags)


def grounded_triples(extraction: Extraction, statuses: list[ClaimStatus]) -> list[tuple[str, str, str]]:
    """The call's non-rejected claims as ``(subject, attribute, value)``."""
    return [
        (claim.subject, claim.attribute, claim.value)
        for claim, status in zip(extraction.claims, statuses)
        if status != "rejected"
    ]


def add_timeline(store: GraphStore, incident_id: str, at: datetime, event: str, call_id: str | None) -> None:
    store.append_timeline(incident_id, TimelineEntry(t=at, event=event, call_id=call_id))


# ---------------------------------------------------------------------------
# Snapshots for the pure functions
# ---------------------------------------------------------------------------


def call_features(
    call: CallIn,
    extraction: Extraction,
    statuses: list[ClaimStatus],
    location: ResolvedLocation,
    reference: ReferenceData,
) -> CallFeatures:
    return CallFeatures(
        call_id="incoming",
        received_at=call.received_at,
        incident_type=extraction.incident_type,
        location=location,
        psap_id=call.psap_id,
        values_by_key=values_by_key(grounded_triples(extraction, statuses)),
        street_names=mention_streets(extraction.location, reference),
    )


def incident_candidate(store: GraphStore, incident: StoredIncident, reference: ReferenceData) -> IncidentCandidate:
    """Entity values come from confirmed (non-provisional, non-rejected) claims."""
    calls = store.calls_for_incident(incident.id)
    claims = store.claims_for_incident(incident.id)
    streets: set[str] = set()
    for call in calls:
        streets |= mention_streets(call.extraction.location, reference)
    return IncidentCandidate(
        incident_id=incident.id,
        incident_type=incident.type,
        last_seen=incident.last_seen,
        location=incident.location,
        psap_ids=frozenset(call.psap_id for call in calls),
        values_by_key=values_by_key((c.subject, c.attribute, c.value) for c in claims),
        street_names=frozenset(streets),
    )


def incident_snapshot(store: GraphStore, incident: StoredIncident) -> prio.IncidentSnapshot:
    """What the incident knew before the call (provisional claims included)."""
    calls = store.calls_for_incident(incident.id)
    claims = store.claims_for_incident(incident.id, include_provisional=True)
    return prio.IncidentSnapshot.build(
        incident.id,
        incident.location,
        [(c.subject, c.attribute, c.value) for c in claims],
        merged_flags(call.flags for call in calls),
    )


# ---------------------------------------------------------------------------
# Recomputation after any change to an incident's calls
# ---------------------------------------------------------------------------


def _best_location(calls: list[StoredCall]) -> ResolvedLocation:
    """Highest-confidence location, preferring ones with coordinates; ties go
    to the earliest call (calls are in arrival order)."""
    with_coords = [call for call in calls if call.location.coords() is not None]
    pool = with_coords or calls
    best = pool[0]
    for call in pool[1:]:
        if call.location.confidence > best.location.confidence:
            best = call
    return best.location


def refresh_header(deps: FlowDeps, incident_id: str) -> StoredIncident:
    """Type and severity of the most severe non-provisional call, flags OR'd
    over those calls, first/last seen over all calls, best location."""
    store = deps.store
    calls = store.calls_for_incident(incident_id)
    incident = store.require_incident(incident_id)
    if not calls:
        return incident
    basis = [call for call in calls if not call.is_provisional()] or calls
    most_severe = basis[0]
    for call in basis[1:]:
        if call_severity(call) > call_severity(most_severe):
            most_severe = call
    store.set_incident_header(
        incident_id,
        incident_type=most_severe.extraction.incident_type,
        severity=call_severity(most_severe),
        flags=merged_flags(call.flags for call in basis),
        first_seen=min(call.received_at for call in calls),
        last_seen=max(call.received_at for call in calls),
        location=_best_location(basis),
    )
    return store.require_incident(incident_id)


def reweigh(deps: FlowDeps, incident_id: str) -> None:
    """Recompute every claim weight, the consensus and the contradictions."""
    store = deps.store
    calls = store.calls_for_incident(incident_id)
    if not calls:
        store.set_consensus(incident_id, [])
        store.set_contradictions(incident_id, [])
        return
    repeats = weigh.repeat_callers([(c.id, c.caller_hash, c.received_at) for c in calls])
    now = max(call.received_at for call in calls)

    evidence: list[weigh.ClaimEvidence] = []
    for call in calls:
        for claim in store.claims_for_call(call.id):
            item = weigh.ClaimEvidence(
                claim_id=claim.id,
                call_id=call.id,
                subject=claim.subject,
                attribute=claim.attribute,
                value=claim.value,
                first_hand=claim.first_hand,
                status=claim.status,
                provisional=claim.provisional,
                caller_role=call.extraction.caller_role,
                received_at=call.received_at,
                repeat_caller=call.id in repeats,
            )
            evidence.append(item)
            weight = weigh.claim_weight(item, now)
            if weight != claim.weight:
                store.replace_claim(claim.model_copy(update={"weight": weight}))

    store.set_consensus(incident_id, weigh.consensus(evidence, now))
    found, pairs = weigh.contradictions(evidence, now)
    store.set_contradictions(incident_id, found)
    store.replace_contradiction_edges([item.claim_id for item in evidence], pairs)


def refresh_dispatch(deps: FlowDeps, incident_id: str, at: datetime, call_id: str | None) -> bool:
    """Rebuild the dispatch package and suggested leads. Returns True when the
    incident became dispatch-ready for the first time."""
    store = deps.store
    reference = deps.reference()
    incident = store.require_incident(incident_id)
    calls = [call for call in store.calls_for_incident(incident_id) if not call.is_provisional()]
    package = dispatch_rules.build_package(
        incident_type=incident.type,
        flags=incident.flags,
        location=incident.location,
        consensus=incident.consensus,
        calls=[
            dispatch_rules.CallFacts(call.extraction.incident_type, call.flags, call.location.is_resolved())
            for call in calls
        ],
        psap_id=calls[0].psap_id if calls else None,
        reference=reference,
    )
    ready_at = at if dispatch_rules.is_dispatch_ready(incident.location, incident.type) else None
    became_ready = store.set_dispatch(incident_id, package, ready_at=ready_at)
    if became_ready:
        add_timeline(store, incident_id, at, "Dispatch ready", call_id)

    refs = [
        dispatch_rules.ClaimRef(claim.id, claim.subject, claim.attribute, claim.value)
        for claim in store.claims_for_incident(incident_id)
    ]
    for suggestion in dispatch_rules.suggest_leads(incident.consensus, refs):
        store.upsert_suggested_lead(
            incident_id, suggestion.key, suggestion.description, list(suggestion.source_claim_ids)
        )
    return became_ready


def recompute_incident(deps: FlowDeps, incident_id: str, at: datetime, call_id: str | None) -> None:
    """Header, weights and consensus, then dispatch, in dependency order."""
    refresh_header(deps, incident_id)
    reweigh(deps, incident_id)
    refresh_dispatch(deps, incident_id, at, call_id)
