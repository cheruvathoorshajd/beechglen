"""Severity, novelty, call priority and hard overrides.

Implements README -> "6. Prioritize". Pure functions over snapshots.

    P_dup    = p_same if band in {auto, suggest, confirmed} else 0
    priority = severity x (1 - P_dup x (1 - novelty))        shown as 0-100

Repeats sink, new facts rise, and a new weapon, injury, location or hazard
always escalates to at least 0.90. No call is ever removed from the queue;
priority only reorders it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.contracts import Flags, OverrideReason, QueueItem, ResolvedLocation
from app.geo import haversine_m
from app.pipeline.link import GEO_CORE_FRACTION

SEVERITY_BY_TYPE: dict[str, float] = {
    "shooting": 1.0,
    "stabbing": 1.0,
    "fire": 0.95,
    "medical": 0.85,
    "robbery": 0.80,
    "assault": 0.75,
    "vehicle_crash": 0.60,
    "disturbance": 0.40,
    "suspicious_activity": 0.30,
    "other": 0.30,
}
FLOOR_CRITICAL = 1.0  # not_breathing or trapped
FLOOR_WEAPON = 0.90
FLOOR_INJURY = 0.85
CHILD_BONUS = 0.05

#: Hard overrides lift a call's priority to at least this.
OVERRIDE_FLOOR = 0.90

DUPLICATE_BANDS = frozenset({"auto", "suggest", "confirmed"})
INJURY_CONDITIONS = frozenset({"not_moving", "unconscious", "bleeding", "not_breathing", "injured"})
FIRE_HAZARDS = frozenset({"fire", "smoke"})

ClaimKey = tuple[str, str]
ClaimTriple = tuple[str, str, str]  # (subject, attribute, value)


# ---------------------------------------------------------------------------
# Severity
# ---------------------------------------------------------------------------


def severity(incident_type: str, flags: Flags) -> float:
    """Base severity by type, raised by risk flags."""
    value = SEVERITY_BY_TYPE.get(incident_type, SEVERITY_BY_TYPE["other"])
    if flags.not_breathing or flags.trapped:
        value = max(value, FLOOR_CRITICAL)
    if flags.weapon_present:
        value = max(value, FLOOR_WEAPON)
    if flags.injuries_reported:
        value = max(value, FLOOR_INJURY)
    if flags.child_involved:
        value += CHILD_BONUS
    return round(min(1.0, value), 4)


# ---------------------------------------------------------------------------
# Snapshot of the incident as it was before the call
# ---------------------------------------------------------------------------


def _injury_count(value: str) -> int | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else None


@dataclass(frozen=True, slots=True)
class IncidentSnapshot:
    """What the incident already knew when the call arrived.

    ``seen`` includes provisional (suggested-link) claims: they are already in
    front of the operator, so repeating them is not new information.
    """

    incident_id: str
    location: ResolvedLocation
    seen: Mapping[ClaimKey, frozenset[str]] = field(default_factory=dict)
    flags: Flags = field(default_factory=Flags)

    @classmethod
    def build(
        cls,
        incident_id: str,
        location: ResolvedLocation,
        claims: Iterable[ClaimTriple],
        flags: Flags,
    ) -> IncidentSnapshot:
        seen: dict[ClaimKey, set[str]] = {}
        for subject, attribute, value in claims:
            seen.setdefault((subject, attribute), set()).add(value)
        return cls(
            incident_id=incident_id,
            location=location,
            seen={key: frozenset(values) for key, values in seen.items()},
            flags=flags,
        )

    def values_for(self, attribute: str) -> set[str]:
        """Every value seen for ``attribute`` across all subjects."""
        found: set[str] = set()
        for (_, attr), values in self.seen.items():
            if attr == attribute:
                found |= values
        return found

    def max_injury_count(self) -> int | None:
        counts = [c for c in (_injury_count(v) for v in self.values_for("injury_count")) if c is not None]
        return max(counts) if counts else None

    def has_injury(self) -> bool:
        return (
            self.flags.injuries_reported
            or self.flags.not_breathing
            or bool(self.values_for("victim_condition"))
            or (self.max_injury_count() or 0) > 0
        )

    def has_fire_or_smoke(self) -> bool:
        return self.flags.fire_or_smoke or bool(self.values_for("hazard") & FIRE_HAZARDS)

    def has_trapped(self) -> bool:
        return self.flags.trapped


# ---------------------------------------------------------------------------
# Novelty and overrides
# ---------------------------------------------------------------------------


def location_is_new(
    call_location: ResolvedLocation,
    incident_location: ResolvedLocation,
    radius_m: float,
) -> bool | None:
    """True when the call is farther than the geo core radius (0.4 R).

    None when either side has no coordinates, so the location is not an item.
    """
    a, b = call_location.coords(), incident_location.coords()
    if a is None or b is None:
        return None
    return haversine_m(a, b) > GEO_CORE_FRACTION * radius_m


def novelty(
    claims: Sequence[ClaimTriple],
    call_location: ResolvedLocation,
    snapshot: IncidentSnapshot,
    radius_m: float,
) -> float:
    """Share of the call's items the incident did not already know.

    Items are the call's non-rejected claims plus its location (when both the
    call and the incident have coordinates).
    """
    total = 0
    new = 0
    for subject, attribute, value in claims:
        total += 1
        if value not in snapshot.seen.get((subject, attribute), frozenset()):
            new += 1
    moved = location_is_new(call_location, snapshot.location, radius_m)
    if moved is not None:
        total += 1
        new += 1 if moved else 0
    return round(new / max(1, total), 4)


def override_reasons(
    claims: Sequence[ClaimTriple],
    flags: Flags,
    call_location: ResolvedLocation,
    snapshot: IncidentSnapshot,
    radius_m: float,
) -> list[OverrideReason]:
    """Hard overrides for a call linked to an existing incident."""
    reasons: list[OverrideReason] = []

    weapons = {value for _, attribute, value in claims if attribute == "weapon"}
    if (weapons - snapshot.values_for("weapon")) or (flags.weapon_present and not snapshot.flags.weapon_present):
        reasons.append("new_weapon")

    conditions = {value for _, attribute, value in claims if attribute == "victim_condition"}
    counts = [c for c in (_injury_count(v) for _, a, v in claims if a == "injury_count") if c is not None]
    call_injured = (
        flags.injuries_reported
        or flags.not_breathing
        or bool(conditions & INJURY_CONDITIONS)
        or any(count > 0 for count in counts)
    )
    if call_injured and not snapshot.has_injury():
        reasons.append("new_injury")
    previous = snapshot.max_injury_count()
    if previous is not None and counts and max(counts) > previous:
        reasons.append("injury_increase")

    if location_is_new(call_location, snapshot.location, radius_m):
        reasons.append("new_location")

    hazards = {value for _, attribute, value in claims if attribute == "hazard"}
    new_fire = (flags.fire_or_smoke or bool(hazards & FIRE_HAZARDS)) and not snapshot.has_fire_or_smoke()
    new_trapped = flags.trapped and not snapshot.has_trapped()
    if new_fire or new_trapped:
        reasons.append("new_hazard")

    return reasons


# ---------------------------------------------------------------------------
# Priority
# ---------------------------------------------------------------------------


def priority(
    severity_value: float,
    band: str,
    p_same: float,
    novelty_value: float,
    reasons: Sequence[str] = (),
) -> float:
    """Information-gain priority in [0, 1], with the hard-override floor."""
    p_dup = p_same if band in DUPLICATE_BANDS else 0.0
    value = severity_value * (1.0 - p_dup * (1.0 - novelty_value))
    if any(reason != "new_incident" for reason in reasons):
        value = max(value, OVERRIDE_FLOOR)
    return max(0.0, min(1.0, value))


def to_display(value: float) -> int:
    """Priority on the 0-100 scale, rounded half up."""
    return int(max(0.0, min(1.0, value)) * 100 + 0.5)


def queue_order(items: Iterable[QueueItem]) -> list[QueueItem]:
    """Priority descending, then oldest first. Nothing is ever filtered out."""
    return sorted(items, key=lambda item: (-item.priority, item.received_at, item.call_id))
