"""Dispatch package, recommended units, agency routing and suggested leads.

Implements README -> "7. Dispatch". Pure: takes the incident header, its
consensus and the reference tables, and returns contract objects. Unit
recommendations come from ``data/dispatch_rules.json`` and are illustrative;
real protocols vary by agency.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from app.contracts import (
    AttributeConsensus,
    DispatchField,
    DispatchPackage,
    Flags,
    ResolvedLocation,
)
from app.pipeline.weigh import consensus_lookup
from app.reference import ReferenceData

#: Location confidence needed before an incident counts as dispatch-ready.
DISPATCH_READY_CONFIDENCE = 0.8

FIRE_TYPES = frozenset({"fire", "vehicle_crash"})
EMS_TYPES = frozenset({"medical", "fire", "vehicle_crash", "shooting", "stabbing"})

PARTY_SUBJECTS = ("suspect", "suspect_2", "vehicle", "vehicle_2")
SUBJECT_LABELS = {
    "suspect": "suspect",
    "suspect_2": "second suspect",
    "vehicle": "vehicle",
    "vehicle_2": "second vehicle",
    "victim": "victim",
    "scene": "scene",
}
VEHICLE_ATTRIBUTES = ("vehicle_color", "vehicle_make", "vehicle_model", "vehicle_type")
SUMMARY_ATTRIBUTES = frozenset({"weapon", "injury_count", "victim_condition", "hazard"})


@dataclass(frozen=True, slots=True)
class CallFacts:
    """Per-call facts dispatch counts sources from (non-provisional calls only)."""

    incident_type: str
    flags: Flags
    located: bool


@dataclass(frozen=True, slots=True)
class ClaimRef:
    """A consensus-eligible claim, for lead provenance."""

    claim_id: str
    subject: str
    attribute: str
    value: str


@dataclass(frozen=True, slots=True)
class LeadSuggestion:
    """A suggested lead. ``key`` is stable, so a lead is updated, not duplicated."""

    key: str
    description: str
    source_claim_ids: tuple[str, ...]


# ---------------------------------------------------------------------------
# Readiness and routing
# ---------------------------------------------------------------------------


def is_dispatch_ready(location: ResolvedLocation, incident_type: str) -> bool:
    """Location confidence at least 0.8 and a known incident type."""
    return location.confidence >= DISPATCH_READY_CONFIDENCE and incident_type != "other"


def recommended_units(
    incident_type: str,
    flags: Flags,
    location: ResolvedLocation,
    reference: ReferenceData,
) -> tuple[str, list[str]]:
    """First matching rule in dispatch_rules.json: ``(rule_id, units)``."""
    rule = reference.dispatch_rules.first_match(incident_type, flags.model_dump(), location.kind)
    return rule.id, list(rule.units)


def route_agencies(
    incident_type: str,
    flags: Flags,
    location: ResolvedLocation,
    units: Sequence[str],
    psap_id: str | None,
    reference: ReferenceData,
) -> list[str]:
    """Highway -> State Police; MBTA station -> MBTA Transit Police; campus ->
    campus police; otherwise the town's police. Fire and EMS by type, flags and
    the recommended units."""
    agencies = reference.agencies
    town = location.town or agencies.town_for_psap(psap_id)

    police = None
    if location.kind == "highway":
        police = agencies.get("state-police")
    elif location.agency_hint:
        police = agencies.get(location.agency_hint)
    if police is None:
        police = agencies.police_for_town(town)

    units_text = " ".join(units).lower()
    needs_fire = (
        incident_type in FIRE_TYPES
        or flags.fire_or_smoke
        or flags.trapped
        or any(word in units_text for word in ("fire", "engine", "ladder"))
    )
    needs_ems = (
        incident_type in EMS_TYPES
        or flags.injuries_reported
        or flags.not_breathing
        or "ems" in units_text
    )

    chosen = [police]
    if needs_fire:
        chosen.append(agencies.fire_for_town(town))
    if needs_ems:
        chosen.append(agencies.ems_for_town(town))

    names: list[str] = []
    for agency in chosen:
        if agency is not None and agency.name not in names:
            names.append(agency.name)
    return names


# ---------------------------------------------------------------------------
# Package
# ---------------------------------------------------------------------------


def _field(name: str, entry: AttributeConsensus) -> DispatchField:
    top = entry.top()
    assert top is not None
    return DispatchField(
        name=name,
        value=top.value,
        confidence=top.share,
        sources=top.sources,
        contested=entry.contested,
    )


def _first_entry(
    consensus: Sequence[AttributeConsensus],
    attributes: Sequence[str],
) -> AttributeConsensus | None:
    """The first consensus entry for any of ``attributes``, in that order."""
    for attribute in attributes:
        for entry in consensus:
            if entry.attribute == attribute and entry.values:
                return entry
    return None


def _summary_field(
    name: str,
    consensus: Sequence[AttributeConsensus],
    attributes: Sequence[str],
    flagged_sources: int,
    flagged_value: str,
) -> DispatchField:
    entry = _first_entry(consensus, attributes)
    if entry is not None:
        return _field(name, entry)
    if flagged_sources:
        return DispatchField(name=name, value=flagged_value, confidence=1.0, sources=flagged_sources)
    return DispatchField(name=name, value="none reported", confidence=0.0, sources=0)


def build_package(
    *,
    incident_type: str,
    flags: Flags,
    location: ResolvedLocation,
    consensus: Sequence[AttributeConsensus],
    calls: Sequence[CallFacts],
    psap_id: str | None,
    reference: ReferenceData,
) -> DispatchPackage:
    """Location, type, injuries, weapons, hazards, suspects and vehicles, each
    with its consensus share and source count; contested fields marked."""
    type_sources = sum(1 for call in calls if call.incident_type == incident_type)
    fields = [
        DispatchField(
            name="location",
            value=location.label,
            confidence=location.confidence,
            sources=sum(1 for call in calls if call.located),
            contested=location.ambiguous,
        ),
        DispatchField(
            name="type",
            value=incident_type,
            confidence=round(type_sources / len(calls), 4) if calls else 0.0,
            sources=type_sources,
        ),
        _summary_field(
            "injuries",
            consensus,
            ("injury_count", "victim_condition"),
            sum(1 for c in calls if c.flags.injuries_reported or c.flags.not_breathing),
            "reported",
        ),
        _summary_field(
            "weapons",
            consensus,
            ("weapon",),
            sum(1 for c in calls if c.flags.weapon_present),
            "reported",
        ),
    ]

    hazard = _first_entry(consensus, ("hazard",))
    fire_sources = sum(1 for c in calls if c.flags.fire_or_smoke)
    if hazard is not None:
        fields.append(_field("hazard", hazard))
    elif fire_sources:
        fields.append(DispatchField(name="hazard", value="fire or smoke", confidence=1.0, sources=fire_sources))
    trapped_sources = sum(1 for c in calls if c.flags.trapped)
    if trapped_sources:
        fields.append(DispatchField(name="trapped", value="people reported trapped", confidence=1.0, sources=trapped_sources))

    for subject in PARTY_SUBJECTS:
        for entry in consensus:
            if entry.subject == subject and entry.values and entry.attribute not in SUMMARY_ATTRIBUTES:
                fields.append(_field(f"{subject}.{entry.attribute}", entry))

    rule_id, units = recommended_units(incident_type, flags, location, reference)
    return DispatchPackage(
        fields=fields,
        recommended_units=units,
        agencies=route_agencies(incident_type, flags, location, units, psap_id, reference),
        rule_id=rule_id,
        illustrative=True,
    )


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------


def suggest_leads(
    consensus: Sequence[AttributeConsensus],
    claims: Sequence[ClaimRef],
) -> list[LeadSuggestion]:
    """Leads from plates, vehicle attributes, direction of travel and suspect
    location. Status stays ``suggested`` until an officer accepts one."""
    index = consensus_lookup(consensus)
    by_key: dict[tuple[str, str], list[str]] = defaultdict(list)
    by_value: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for claim in claims:
        by_key[(claim.subject, claim.attribute)].append(claim.claim_id)
        by_value[(claim.subject, claim.attribute, claim.value)].append(claim.claim_id)

    leads: list[LeadSuggestion] = []
    for subject in ("vehicle", "vehicle_2"):
        entry = index.get((subject, "vehicle_plate"))
        for share in entry.values if entry else ():
            leads.append(
                LeadSuggestion(
                    key=f"plate:{share.value}",
                    description=f"Run plate {share.value.upper()}",
                    source_claim_ids=tuple(by_value[(subject, "vehicle_plate", share.value)]),
                )
            )

    for subject in ("vehicle", "vehicle_2"):
        parts = [
            index[(subject, attribute)].values[0].value
            for attribute in VEHICLE_ATTRIBUTES
            if (subject, attribute) in index and index[(subject, attribute)].values
        ]
        if parts:
            sources = [cid for attribute in VEHICLE_ATTRIBUTES for cid in by_key[(subject, attribute)]]
            leads.append(
                LeadSuggestion(
                    key=f"vehicle:{subject}",
                    description=f"Identify the {SUBJECT_LABELS[subject]}: {' '.join(parts)}",
                    source_claim_ids=tuple(sources),
                )
            )

    templates = (
        ("direction_of_travel", "Search along the {label}'s direction of travel: {value}"),
        ("suspect_location", "Check the {label}'s last reported location: {value}"),
    )
    for subject in ("suspect", "suspect_2"):
        for attribute, template in templates:
            entry = index.get((subject, attribute))
            if entry is None or not entry.values:
                continue
            leads.append(
                LeadSuggestion(
                    key=f"{attribute}:{subject}",
                    description=template.format(label=SUBJECT_LABELS[subject], value=entry.values[0].value),
                    source_claim_ids=tuple(by_key[(subject, attribute)]),
                )
            )
    return leads
