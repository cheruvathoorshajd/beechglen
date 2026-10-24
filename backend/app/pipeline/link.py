"""Incident linking: does this call describe an event we already know about?

Implements README -> "4. Link". Pure and store-free: the caller builds
:class:`CallFeatures` and :class:`IncidentCandidate` snapshots, this module
scores them. That keeps every number here testable without a graph.

Score:

    geo    = 1.0 if d <= 0.4R, else max(0, 1 - (d - 0.4R) / 0.6R)
    time   = max(0, 1 - dt_min / window_min)
    type   = 1.0 same | 0.6 compatible | 0.3 vague | 0.0 incompatible
    entity = mean over shared (subject, attribute) keys
    p_same = (0.35 geo + 0.25 time + 0.20 type + 0.20 entity) / sum(available weights)

Unavailable components are dropped and the remaining weights renormalized, so a
call with no coordinates is not punished for the missing ``geo`` term.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from app.contracts import (
    Band,
    IncidentType,
    LinkComponents,
    ResolvedLocation,
    RuntimeSettings,
    is_identifying,
)
from app.geo import haversine_m
from app.pipeline.locate import MIN_CONFIDENCE_FOR_AUTO_LINK

ClaimKey = tuple[str, str]
ValuesByKey = Mapping[ClaimKey, frozenset[str]]

# Component weights (README -> "4. Link").
WEIGHT_GEO = 0.35
WEIGHT_TIME = 0.25
WEIGHT_TYPE = 0.20
WEIGHT_ENTITY = 0.20

#: Inside this fraction of the radius, geo scores a flat 1.0. Also the radius
#: used by novelty to decide whether a caller is "somewhere else".
GEO_CORE_FRACTION = 0.4

#: Hard ceiling applied when two incident types cannot be the same event.
INCOMPATIBLE_TYPE_CAP = 0.49

GATE_INCOMPATIBLE_TYPE = "incompatible_type_cap"
GATE_LOW_LOCATION_CONFIDENCE = "low_location_confidence"

_VIOLENT: frozenset[str] = frozenset({"shooting", "stabbing", "robbery", "assault"})
_VAGUE: frozenset[str] = frozenset({"disturbance", "suspicious_activity", "other"})

#: Symmetric compatibility map. Anything absent is incompatible.
_COMPATIBLE: dict[str, frozenset[str]] = {
    "shooting": _VIOLENT | {"medical"},
    "stabbing": _VIOLENT | {"medical"},
    "robbery": _VIOLENT | {"medical"},
    "assault": _VIOLENT | {"medical"},
    "medical": _VIOLENT | {"vehicle_crash", "fire"},
    "vehicle_crash": frozenset({"medical", "fire"}),
    "fire": frozenset({"medical", "vehicle_crash"}),
}


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CallFeatures:
    """Everything linking needs to know about the incoming call."""

    call_id: str
    received_at: datetime
    incident_type: IncidentType
    location: ResolvedLocation
    psap_id: str
    values_by_key: ValuesByKey = field(default_factory=dict)
    street_names: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class IncidentCandidate:
    """Read-only snapshot of an open incident."""

    incident_id: str
    incident_type: IncidentType
    last_seen: datetime
    location: ResolvedLocation
    psap_ids: frozenset[str] = frozenset()
    values_by_key: ValuesByKey = field(default_factory=dict)
    street_names: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """One scored pairing of a call and an incident."""

    incident_id: str
    p_same: float
    components: LinkComponents
    gates: tuple[str, ...]
    distance_m: float | None
    same_psap: bool
    last_seen: datetime

    def sort_key(self) -> tuple[float, int, float]:
        """Highest score first; ties go to the same PSAP, then the most recent."""
        return (self.p_same, 1 if self.same_psap else 0, self.last_seen.timestamp())


# ---------------------------------------------------------------------------
# Component scores
# ---------------------------------------------------------------------------


def type_score(a: str, b: str) -> float:
    """Type agreement between a call and an incident."""
    if a == b:
        return 1.0
    if a in _VAGUE or b in _VAGUE:
        return 0.3
    if b in _COMPATIBLE.get(a, frozenset()):
        return 0.6
    return 0.0


def types_are_incompatible(a: str, b: str) -> bool:
    """True when the two types can never describe one event."""
    return type_score(a, b) == 0.0


def geo_score(distance_m: float, radius_m: float) -> float:
    """Flat 1.0 inside the core radius, then a linear taper to 0 at ``radius_m``."""
    if radius_m <= 0:
        return 0.0
    core = GEO_CORE_FRACTION * radius_m
    if distance_m <= core:
        return 1.0
    taper = (1.0 - GEO_CORE_FRACTION) * radius_m
    return max(0.0, 1.0 - (distance_m - core) / taper)


def time_score(delta_minutes: float, window_min: float) -> float:
    """Linear decay across the time window."""
    if window_min <= 0:
        return 0.0
    return max(0.0, 1.0 - abs(delta_minutes) / window_min)


def entity_score(call_values: ValuesByKey, incident_values: ValuesByKey) -> float | None:
    """Mean agreement over the ``(subject, attribute)`` keys both sides mention.

    Returns None when they share no keys, so the component is dropped rather
    than scored as a disagreement.
    """
    shared = [key for key in call_values if key in incident_values]
    if not shared:
        return None

    total = 0.0
    for key in shared:
        known = incident_values[key]
        fallback = 0.0 if is_identifying(key[1]) else 0.5
        total += max(
            (1.0 if value in known else fallback) for value in call_values[key]
        ) if call_values[key] else fallback
    return total / len(shared)


def combine(components: LinkComponents) -> float:
    """Weighted mean of the available components, renormalized."""
    weights = {
        "geo": WEIGHT_GEO,
        "time": WEIGHT_TIME,
        "type": WEIGHT_TYPE,
        "entity": WEIGHT_ENTITY,
    }
    available = components.available()
    if not available:
        return 0.0
    weighted = sum(weights[name] * value for name, value in available.items())
    total_weight = sum(weights[name] for name in available)
    return weighted / total_weight if total_weight else 0.0


# ---------------------------------------------------------------------------
# Scoring and candidate selection
# ---------------------------------------------------------------------------


def radius_for(location: ResolvedLocation, settings: RuntimeSettings) -> int:
    """Search radius in metres for the call's resolved location kind."""
    return settings.radius_for(location.kind)


def score_candidate(
    call: CallFeatures,
    candidate: IncidentCandidate,
    settings: RuntimeSettings,
) -> ScoredCandidate:
    """Score one call/incident pairing, applying the incompatible-type gate."""
    window_min = settings.effective_window_min()
    radius_m = radius_for(call.location, settings)
    gates: list[str] = []

    call_coords = call.location.coords()
    incident_coords = candidate.location.coords()
    distance_m: float | None = None
    geo: float | None = None
    if call_coords is not None and incident_coords is not None:
        distance_m = haversine_m(call_coords, incident_coords)
        geo = geo_score(distance_m, radius_m)

    delta_minutes = abs((call.received_at - candidate.last_seen).total_seconds()) / 60.0
    components = LinkComponents(
        geo=geo,
        time=time_score(delta_minutes, window_min),
        type=type_score(call.incident_type, candidate.incident_type),
        entity=entity_score(call.values_by_key, candidate.values_by_key),
    )

    p_same = combine(components)

    if types_are_incompatible(call.incident_type, candidate.incident_type):
        # Different emergencies are never merged, however well everything else
        # lines up.
        p_same = min(p_same, INCOMPATIBLE_TYPE_CAP)
        gates.append(GATE_INCOMPATIBLE_TYPE)

    return ScoredCandidate(
        incident_id=candidate.incident_id,
        p_same=round(p_same, 4),
        components=components,
        gates=tuple(gates),
        distance_m=distance_m,
        same_psap=call.psap_id in candidate.psap_ids,
        last_seen=candidate.last_seen,
    )


def select_candidates(
    call: CallFeatures,
    open_candidates: list[IncidentCandidate],
    settings: RuntimeSettings,
) -> list[IncidentCandidate]:
    """Narrow open incidents to plausible matches before scoring.

    Three regimes, per README:

    * **Located call** - incidents within radius R, H3 pre-filtered then
      distance-checked exactly.
    * **Ambiguous location** - incidents sharing a candidate street name,
      restricted to the same PSAP when any such incident exists, because a call
      answered by the Boston centre is most likely in Boston.
    * **Unknown location** - incidents with a compatible type.
    """
    coords = call.location.coords()

    if coords is not None and not call.location.ambiguous:
        radius_m = radius_for(call.location, settings)
        within: list[IncidentCandidate] = []
        for candidate in open_candidates:
            candidate_coords = candidate.location.coords()
            if candidate_coords is None:
                continue
            if haversine_m(coords, candidate_coords) <= radius_m:
                within.append(candidate)
        return within

    if call.location.ambiguous:
        street_matches = [
            candidate
            for candidate in open_candidates
            if call.street_names & candidate.street_names
        ]
        same_psap = [c for c in street_matches if call.psap_id in c.psap_ids]
        return same_psap or street_matches

    return [
        candidate
        for candidate in open_candidates
        if not types_are_incompatible(call.incident_type, candidate.incident_type)
    ]


def band_for(
    p_same: float,
    location: ResolvedLocation,
    settings: RuntimeSettings,
) -> tuple[Band, list[str]]:
    """Map a score to a band, applying the location-confidence gate."""
    gates: list[str] = []
    auto_threshold = settings.effective_auto_threshold()

    if p_same < settings.suggest_threshold:
        return "new", gates

    band: Band = "auto" if p_same >= auto_threshold else "suggest"

    if band == "auto" and location.confidence < MIN_CONFIDENCE_FOR_AUTO_LINK:
        # An unresolved location is never auto-linked; a human confirms.
        band = "suggest"
        gates.append(GATE_LOW_LOCATION_CONFIDENCE)

    return band, gates


@dataclass(frozen=True, slots=True)
class LinkOutcome:
    """Result of linking: either the winning candidate, or a new incident."""

    band: Band
    p_same: float
    components: LinkComponents
    gates: tuple[str, ...]
    incident_id: str | None
    distance_m: float | None = None
    considered: int = 0

    def creates_incident(self) -> bool:
        return self.incident_id is None


def decide(
    call: CallFeatures,
    open_candidates: list[IncidentCandidate],
    settings: RuntimeSettings,
) -> LinkOutcome:
    """Pick the best incident for a call, or decide it is something new."""
    candidates = select_candidates(call, open_candidates, settings)
    scored = [score_candidate(call, candidate, settings) for candidate in candidates]

    if not scored:
        return LinkOutcome(
            band="new",
            p_same=0.0,
            components=LinkComponents(),
            gates=(),
            incident_id=None,
            considered=0,
        )

    best = max(scored, key=ScoredCandidate.sort_key)
    band, band_gates = band_for(best.p_same, call.location, settings)
    gates = tuple((*best.gates, *band_gates))

    if band == "new":
        return LinkOutcome(
            band="new",
            p_same=best.p_same,
            components=best.components,
            gates=gates,
            incident_id=None,
            distance_m=best.distance_m,
            considered=len(scored),
        )

    return LinkOutcome(
        band=band,
        p_same=best.p_same,
        components=best.components,
        gates=gates,
        incident_id=best.incident_id,
        distance_m=best.distance_m,
        considered=len(scored),
    )
