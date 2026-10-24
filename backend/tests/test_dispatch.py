"""Dispatch package, units, routing and leads (README -> "7. Dispatch")."""

from __future__ import annotations

from app.contracts import AttributeConsensus, Flags, ResolvedLocation, ValueShare
from app.pipeline.dispatch import (
    CallFacts,
    ClaimRef,
    build_package,
    is_dispatch_ready,
    recommended_units,
    route_agencies,
    suggest_leads,
)
from app.reference import reference_data

PIKE = ResolvedLocation(lat=42.1730, lng=-72.3280, kind="highway", label="I-90 EB Exit 63", town="Palmer",
                        confidence=0.9, agency_hint="state-police")
BOYLSTON = ResolvedLocation(lat=42.3470, lng=-71.0874, kind="intersection", label="Mass Ave & Boylston St, Boston",
                            town="Boston", confidence=0.9)
WESTLAND = ResolvedLocation(lat=42.3446, lng=-71.0880, kind="street", label="Westland Ave, Boston", town="Boston",
                            confidence=0.8)


def share(value, share_value, sources):
    return ValueShare(value=value, share=share_value, sources=sources, first_hand_sources=sources)


def test_highway_crash_with_injuries_recommends_ems_fire_and_state_police():
    flags = Flags(injuries_reported=True)
    rule_id, units = recommended_units("vehicle_crash", flags, PIKE, reference_data())
    assert rule_id == "crash_highway_injuries"
    assert units == ["2 EMS", "1 Fire", "State Police"]
    agencies = route_agencies("vehicle_crash", flags, PIKE, units, "msp-pike", reference_data())
    assert agencies == ["Massachusetts State Police", "Local Fire Department", "Local EMS"]


def test_fire_with_trapped_people():
    flags = Flags(fire_or_smoke=True, trapped=True)
    rule_id, units = recommended_units("fire", flags, WESTLAND, reference_data())
    assert rule_id == "fire_trapped"
    assert units == ["3 Engine", "1 Ladder", "2 EMS", "1 Police"]
    assert route_agencies("fire", flags, WESTLAND, units, "boston-ecc", reference_data()) == [
        "Boston Police", "Boston Fire", "Boston EMS",
    ]


def test_armed_robbery_routes_town_police_with_ems_standby():
    flags = Flags(weapon_present=True)
    rule_id, units = recommended_units("robbery", flags, BOYLSTON, reference_data())
    assert (rule_id, units) == ("violent_weapon", ["3 Police", "1 EMS standby"])
    assert route_agencies("robbery", flags, BOYLSTON, units, "boston-ecc", reference_data()) == ["Boston Police", "Boston EMS"]
    assert recommended_units("robbery", Flags(), BOYLSTON, reference_data()) == ("violent", ["2 Police"])
    assert recommended_units("suspicious_activity", Flags(), BOYLSTON, reference_data()) == ("default", ["1 Police"])


def test_mbta_station_and_campus_route_to_their_police():
    station = ResolvedLocation(lat=42.348, lng=-71.0877, kind="landmark", label="Hynes", town="Boston",
                               confidence=0.9, agency_hint="mbta-transit-police")
    campus = ResolvedLocation(lat=42.3398, lng=-71.0892, kind="landmark", label="Northeastern", town="Boston",
                              confidence=0.9, agency_hint="northeastern-police")
    assert route_agencies("assault", Flags(), station, ["2 Police"], "boston-ecc", reference_data()) == ["MBTA Transit Police"]
    assert route_agencies("assault", Flags(), campus, ["2 Police"], "boston-ecc", reference_data()) == ["Northeastern University Police"]


def test_unknown_town_falls_back_to_the_psap_town():
    unknown = ResolvedLocation(kind="unknown", label="Unknown location", confidence=0.0)
    assert route_agencies("assault", Flags(), unknown, ["2 Police"], "brookline-local", reference_data()) == ["Brookline Police"]


def test_dispatch_ready_needs_confidence_and_known_type():
    assert is_dispatch_ready(BOYLSTON, "robbery")
    assert not is_dispatch_ready(BOYLSTON, "other")
    assert not is_dispatch_ready(BOYLSTON.model_copy(update={"confidence": 0.6}), "robbery")


def test_package_fields_carry_share_sources_and_contested():
    consensus = [
        AttributeConsensus(subject="suspect", attribute="upper_clothing_color", contested=False,
                           values=[share("white", 0.83, 7), share("black", 0.17, 3)]),
        AttributeConsensus(subject="suspect", attribute="weapon", values=[share("knife", 1.0, 1)]),
        AttributeConsensus(subject="vehicle", attribute="vehicle_color", contested=True,
                           values=[share("silver", 0.6, 6), share("white", 0.4, 4)]),
    ]
    calls = [CallFacts("robbery", Flags(weapon_present=True), True)] * 3 + [CallFacts("assault", Flags(), True)]
    package = build_package(incident_type="robbery", flags=Flags(weapon_present=True), location=BOYLSTON,
                            consensus=consensus, calls=calls, psap_id="boston-ecc", reference=reference_data())
    fields = {f.name: f for f in package.fields}
    assert fields["location"].value == BOYLSTON.label and fields["location"].sources == 4
    assert fields["type"].value == "robbery" and fields["type"].confidence == 0.75 and fields["type"].sources == 3
    assert fields["weapons"].value == "knife" and fields["weapons"].sources == 1
    assert fields["injuries"].value == "none reported"
    assert fields["suspect.upper_clothing_color"].value == "white"
    assert fields["suspect.upper_clothing_color"].confidence == 0.83
    assert fields["vehicle.vehicle_color"].contested is True
    assert "suspect.weapon" not in fields
    assert package.illustrative is True and package.rule_id == "violent_weapon"


def test_suggested_leads_from_plates_vehicles_and_movement():
    consensus = [
        AttributeConsensus(subject="vehicle", attribute="vehicle_color", values=[share("silver", 1.0, 2)]),
        AttributeConsensus(subject="vehicle", attribute="vehicle_type", values=[share("suv", 1.0, 2)]),
        AttributeConsensus(subject="vehicle", attribute="vehicle_plate", values=[share("abc123", 1.0, 1)]),
        AttributeConsensus(subject="suspect", attribute="direction_of_travel",
                           values=[share("hynes station", 0.7, 2), share("newbury street", 0.3, 1)]),
    ]
    claims = [
        ClaimRef("clm-1", "vehicle", "vehicle_plate", "abc123"),
        ClaimRef("clm-2", "vehicle", "vehicle_color", "silver"),
        ClaimRef("clm-3", "suspect", "direction_of_travel", "hynes station"),
    ]
    leads = {lead.key: lead for lead in suggest_leads(consensus, claims)}
    assert leads["plate:abc123"].description == "Run plate ABC123"
    assert leads["plate:abc123"].source_claim_ids == ("clm-1",)
    assert leads["vehicle:vehicle"].description == "Identify the vehicle: silver suv"
    assert leads["direction_of_travel:suspect"].description.endswith("hynes station")
