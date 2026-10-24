"""Incident linking (README -> "4. Link")."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.contracts import LinkComponents, ResolvedLocation, RuntimeSettings
from app.pipeline.link import (
    GATE_INCOMPATIBLE_TYPE,
    GATE_LOW_LOCATION_CONFIDENCE,
    CallFeatures,
    IncidentCandidate,
    band_for,
    combine,
    decide,
    entity_score,
    geo_score,
    select_candidates,
    type_score,
)

T0 = datetime(2026, 10, 24, 14, 0, tzinfo=timezone(timedelta(hours=-4)))
BOYLSTON = (42.3470, -71.0874)
NEWBURY = (42.3485, -71.0878)


def located(coords, kind="intersection", confidence=0.9):
    return ResolvedLocation(lat=coords[0], lng=coords[1], kind=kind, label="x", confidence=confidence)


def ambiguous_washington():
    return ResolvedLocation(
        kind="street",
        label="Washington St",
        confidence=0.3,
        ambiguous=True,
        candidates=["Boston", "Brookline", "Somerville"],
    )


def call(*, at, incident_type="robbery", location=None, psap="boston-ecc", values=None, streets=()):
    return CallFeatures(
        call_id="call",
        received_at=at,
        incident_type=incident_type,
        location=location or located(BOYLSTON),
        psap_id=psap,
        values_by_key=values or {},
        street_names=frozenset(streets),
    )


def incident(incident_id, *, last_seen=T0, incident_type="robbery", location=None, psaps=("boston-ecc",), values=None, streets=()):
    return IncidentCandidate(
        incident_id=incident_id,
        incident_type=incident_type,
        last_seen=last_seen,
        location=location or located(BOYLSTON),
        psap_ids=frozenset(psaps),
        values_by_key=values or {},
        street_names=frozenset(streets),
    )


WHITE = {("suspect", "upper_clothing_color"): frozenset({"white"})}
WHITE_OR_BLACK = {("suspect", "upper_clothing_color"): frozenset({"white", "black"})}


def test_duplicate_at_same_intersection_is_auto():
    outcome = decide(
        call(at=T0 + timedelta(seconds=40), values=WHITE),
        [incident("inc-A", values=WHITE_OR_BLACK)],
        RuntimeSettings(),
    )
    assert outcome.band == "auto"
    assert outcome.incident_id == "inc-A"
    assert outcome.p_same >= 0.95
    assert outcome.components.geo == 1.0
    assert outcome.components.entity == 1.0


def test_incompatible_types_cap_at_049_and_create_a_new_incident():
    outcome = decide(
        call(at=T0 + timedelta(minutes=2), incident_type="fire", location=located(BOYLSTON, "street", 0.8)),
        [incident("inc-A")],
        RuntimeSettings(),
    )
    assert outcome.p_same == pytest.approx(0.49)
    assert outcome.band == "new"
    assert outcome.creates_incident()
    assert GATE_INCOMPATIBLE_TYPE in outcome.gates


def test_ambiguous_location_caps_at_suggest_and_prefers_same_psap():
    boston = incident("inc-D", incident_type="assault", psaps=("boston-ecc",), streets=("washington street",),
                      location=located((42.3555, -71.0605), "street", 0.8))
    brookline = incident("inc-E", incident_type="assault", psaps=("brookline-local",), streets=("washington street",),
                         location=located((42.3326, -71.1166), "street", 0.8))
    incoming = call(at=T0 + timedelta(minutes=2), incident_type="assault", location=ambiguous_washington(),
                    streets=("washington street",))

    candidates = select_candidates(incoming, [boston, brookline], RuntimeSettings())
    assert [c.incident_id for c in candidates] == ["inc-D"]

    outcome = decide(incoming, [boston, brookline], RuntimeSettings())
    assert outcome.band == "suggest"
    assert outcome.incident_id == "inc-D"
    assert outcome.components.geo is None
    assert GATE_LOW_LOCATION_CONFIDENCE in outcome.gates


def test_mass_event_mode_raises_auto_threshold():
    location = located(BOYLSTON)
    assert band_for(0.87, location, RuntimeSettings())[0] == "auto"
    assert band_for(0.87, location, RuntimeSettings(mass_event_mode=True))[0] == "suggest"
    assert band_for(0.91, location, RuntimeSettings(mass_event_mode=True))[0] == "auto"


def test_mass_event_mode_doubles_the_time_window():
    late = call(at=T0 + timedelta(minutes=45))
    assert select_candidates(late, [incident("inc-A")], RuntimeSettings()) == []
    assert len(select_candidates(late, [incident("inc-A")], RuntimeSettings(mass_event_mode=True))) == 1


def test_bands_and_thresholds():
    location = located(BOYLSTON)
    assert band_for(0.85, location, RuntimeSettings())[0] == "auto"
    assert band_for(0.84, location, RuntimeSettings())[0] == "suggest"
    assert band_for(0.50, location, RuntimeSettings())[0] == "suggest"
    assert band_for(0.49, location, RuntimeSettings())[0] == "new"


def test_unavailable_components_are_renormalized():
    components = LinkComponents(geo=None, time=1.0, type=1.0, entity=None)
    assert combine(components) == pytest.approx(1.0)
    components = LinkComponents(geo=0.0, time=1.0, type=1.0, entity=None)
    assert combine(components) == pytest.approx(0.45 / 0.80)


def test_identifying_mismatch_scores_zero_and_perceptual_half():
    plate = {("vehicle", "vehicle_plate"): frozenset({"abc123"})}
    other_plate = {("vehicle", "vehicle_plate"): frozenset({"xyz789"})}
    assert entity_score(plate, other_plate) == 0.0
    black = {("suspect", "upper_clothing_color"): frozenset({"black"})}
    assert entity_score(black, WHITE) == 0.5


def test_mutable_attributes_are_excluded_from_entity_score():
    moving = {("suspect", "suspect_location"): frozenset({"newbury street"})}
    seen = {("suspect", "suspect_location"): frozenset({"hynes station"})}
    assert entity_score(moving, seen) is None


def test_geo_score_core_and_taper():
    assert geo_score(100, 400) == 1.0
    assert geo_score(160, 400) == 1.0
    assert geo_score(280, 400) == pytest.approx(0.5)
    assert geo_score(400, 400) == pytest.approx(0.0)


def test_candidates_outside_radius_are_excluded():
    far = incident("inc-far", location=located((42.3533, -71.0874)))  # about 700 m north
    near = incident("inc-near", location=located(NEWBURY))  # about 170 m
    candidates = select_candidates(call(at=T0 + timedelta(minutes=1)), [far, near], RuntimeSettings())
    assert [c.incident_id for c in candidates] == ["inc-near"]


def test_type_compatibility_table():
    assert type_score("robbery", "assault") == 0.6
    assert type_score("medical", "fire") == 0.6
    assert type_score("vehicle_crash", "fire") == 0.6
    assert type_score("disturbance", "fire") == 0.3
    assert type_score("robbery", "fire") == 0.0
    assert type_score("robbery", "robbery") == 1.0


def test_ties_go_to_same_psap_then_most_recent():
    settings = RuntimeSettings()
    at = T0 + timedelta(minutes=1)
    other_psap = incident("inc-other", psaps=("cambridge-ecc",))
    same_psap = incident("inc-same", psaps=("boston-ecc",))
    assert decide(call(at=at), [other_psap, same_psap], settings).incident_id == "inc-same"

    older = incident("inc-older", last_seen=T0 - timedelta(minutes=10))
    newer = incident("inc-newer", last_seen=T0 + timedelta(minutes=2))
    # Same distance and type; the newer one is also closer in time, so it wins.
    assert decide(call(at=at), [older, newer], settings).incident_id == "inc-newer"
