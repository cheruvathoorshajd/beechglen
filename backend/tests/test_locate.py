"""Massachusetts location resolution (README -> "3. Locate")."""

from __future__ import annotations

import pytest

from app.contracts import LocationMention
from app.pipeline.locate import resolve
from app.reference import reference_data

BOYLSTON = (42.3470, -71.0874)
NEWBURY = (42.3485, -71.0878)
BROOKLINE_VILLAGE = (42.3326, -71.1166)
EXIT_63 = (42.1730, -72.3280)


def test_old_exit_8_and_new_exit_63_are_the_same_point():
    new = resolve(LocationMention(highway_route="I-90", highway_exit="63"))
    old = resolve(LocationMention(highway_route="I-90", highway_exit="8", exit_is_old=True))
    assert new.coords() == old.coords() == EXIT_63
    assert new.kind == old.kind == "highway"
    assert new.confidence == old.confidence == 0.9
    assert new.agency_hint == "state-police"
    assert new.town == "Palmer"


def test_exit_number_tries_new_numbering_then_old():
    location = resolve(LocationMention(highway_route="the Pike", highway_exit="8"))
    assert location.coords() == EXIT_63


@pytest.mark.parametrize("alias", ["Pike", "the Pike", "Mass Pike", "Turnpike", "90", "I-90"])
def test_route_aliases_resolve_to_i90(alias):
    assert reference_data().highways.canonical_route(alias) == "I-90"


@pytest.mark.parametrize("alias", ["128", "95", "Route 128"])
def test_route_aliases_resolve_to_i95(alias):
    assert reference_data().highways.canonical_route(alias) == "I-95"


def test_route_alias_matches_whole_words_only():
    assert reference_data().highways.canonical_route("I-290") != "I-90"


def test_mile_marker_picks_nearest_entry_with_lower_confidence():
    location = resolve(LocationMention(highway_route="I-90", mile_marker=62))
    assert location.coords() == EXIT_63
    assert location.confidence == 0.7


def test_route_plus_town_picks_that_towns_entry():
    location = resolve(LocationMention(highway_route="Mass Pike", town="Palmer"))
    assert location.coords() == EXIT_63
    assert location.confidence == 0.9


def test_route_without_exit_mile_or_town_uses_device_location():
    device = (42.1745, -72.3260)
    location = resolve(LocationMention(highway_route="Turnpike", highway_direction="eastbound"), device)
    assert location.kind == "highway"
    assert location.coords() == device
    assert location.confidence == 0.6
    assert location.agency_hint == "state-police"
    assert location.label.startswith("I-90 EB")


def test_washington_st_with_brookline_device_resolves_to_brookline():
    location = resolve(LocationMention(street="Washington St"), BROOKLINE_VILLAGE)
    assert location.town == "Brookline"
    assert location.kind == "street"
    assert location.confidence == 0.8
    assert not location.ambiguous


def test_washington_st_without_town_or_device_is_ambiguous():
    location = resolve(LocationMention(street="Washington Street"))
    assert location.ambiguous
    assert location.confidence == 0.3
    assert location.coords() is None
    assert sorted(location.candidates) == ["Boston", "Brookline", "Somerville"]


def test_landmark_resolves_with_agency_hint():
    location = resolve(LocationMention(landmark="Hynes station"))
    assert location.kind == "landmark"
    assert location.confidence == 0.9
    assert location.agency_hint == "mbta-transit-police"


def test_landmark_alias_needs_whole_words():
    assert reference_data().landmarks.match("near the neurology clinic") is None


@pytest.mark.parametrize(
    ("street", "cross"),
    [
        ("Mass Ave", "Boylston St"),
        ("Massachusetts Avenue", "Boylston Street"),
        ("Boylston", "Mass Ave"),
    ],
)
def test_intersection_resolves_in_any_spelling(street, cross):
    location = resolve(LocationMention(street=street, cross_street=cross))
    assert location.kind == "intersection"
    assert location.coords() == BOYLSTON
    assert location.confidence == 0.9
    assert location.town == "Boston"


def test_full_street_names_canonicalize_cleanly():
    gazetteer = reference_data().gazetteer
    assert gazetteer.canonical_street("Massachusetts Avenue") == "massachusetts avenue"
    assert gazetteer.canonical_street("Mass Ave") == "massachusetts avenue"
    assert gazetteer.canonical_street("Mass Avenue") == "massachusetts avenue"


def test_street_in_one_town_resolves_without_a_town():
    location = resolve(LocationMention(street="Westland Ave"))
    assert location.kind == "street"
    assert location.town == "Boston"
    assert location.confidence == 0.8


def test_flight_direction_in_raw_words_does_not_relocate_the_call():
    mention = LocationMention(
        street="Mass Ave",
        cross_street="Boylston",
        raw="my store at Mass Ave and Boylston, he ran toward Hynes station",
    )
    location = resolve(mention, BOYLSTON)
    assert location.kind == "intersection"
    assert location.coords() == BOYLSTON


def test_device_only():
    location = resolve(LocationMention(), (42.3600, -71.0700))
    assert location.kind == "device"
    assert location.confidence == 0.6


def test_nothing_resolves_to_unknown():
    location = resolve(LocationMention())
    assert location.kind == "unknown"
    assert location.confidence == 0.0
    assert location.coords() is None
