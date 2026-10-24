"""Severity, novelty, priority and overrides (README -> "6. Prioritize")."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.contracts import Flags, QueueItem, ResolvedLocation
from app.pipeline.priority import (
    IncidentSnapshot,
    novelty,
    override_reasons,
    priority,
    queue_order,
    severity,
    to_display,
)

T0 = datetime(2026, 10, 24, 14, 0, tzinfo=timezone(timedelta(hours=-4)))
BOYLSTON = ResolvedLocation(lat=42.3470, lng=-71.0874, kind="intersection", label="Mass Ave & Boylston", confidence=0.9)
NEWBURY = ResolvedLocation(lat=42.3485, lng=-71.0878, kind="intersection", label="Mass Ave & Newbury", confidence=0.9)
WHITE = ("suspect", "upper_clothing_color", "white")
JACKET = ("suspect", "upper_clothing_type", "jacket")


def robbery_snapshot(**flags):
    return IncidentSnapshot.build("inc-A", BOYLSTON, [WHITE, JACKET, ("suspect", "upper_clothing_color", "black")], Flags(**flags))


# README "Worked example" rows -------------------------------------------------


def test_ninth_robbery_caller_with_nothing_new_sinks_to_3():
    value = priority(0.80, "auto", 0.96, 0.0)
    assert to_display(value) == 3


def test_knife_call_is_floored_at_90():
    value = priority(0.90, "auto", 0.90, 0.5, ["new_weapon"])
    assert to_display(value) == 90


def test_fire_with_people_trapped_is_100():
    fire_severity = severity("fire", Flags(fire_or_smoke=True, trapped=True))
    assert fire_severity == 1.0
    assert to_display(priority(fire_severity, "new", 0.49, 1.0, ["new_incident"])) == 100


# Severity ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("incident_type", "flags", "expected"),
    [
        ("robbery", Flags(), 0.80),
        ("robbery", Flags(weapon_present=True), 0.90),
        ("vehicle_crash", Flags(injuries_reported=True), 0.85),
        ("medical", Flags(not_breathing=True), 1.0),
        ("disturbance", Flags(child_involved=True), 0.45),
        ("shooting", Flags(child_involved=True), 1.0),
        ("other", Flags(), 0.30),
    ],
)
def test_severity_floors_and_child_bonus(incident_type, flags, expected):
    assert severity(incident_type, flags) == pytest.approx(expected)


# Novelty -----------------------------------------------------------------------


def test_repeat_details_have_zero_novelty():
    assert novelty([WHITE, JACKET], BOYLSTON, robbery_snapshot(), 400) == 0.0


def test_new_value_and_new_key_count_as_new():
    claims = [WHITE, ("suspect", "build", "thin"), ("suspect", "upper_clothing_color", "gray")]
    # 2 of 3 claims new, location within the core radius is an item that is not new.
    assert novelty(claims, BOYLSTON, robbery_snapshot(), 400) == pytest.approx(0.5)


def test_location_beyond_core_radius_is_new():
    assert novelty([], NEWBURY, robbery_snapshot(), 400) == 1.0  # about 170 m > 0.4 x 400 m
    assert novelty([], NEWBURY, robbery_snapshot(), 2000) == 0.0


def test_new_incident_priority_uses_full_severity_without_floor():
    assert priority(0.40, "new", 0.0, 1.0, ["new_incident"]) == pytest.approx(0.40)


def test_suggest_band_counts_as_duplicate():
    assert priority(0.80, "suggest", 0.7, 0.0) == pytest.approx(0.80 * 0.3)


# Overrides ---------------------------------------------------------------------


def test_new_weapon_when_the_weapon_was_not_known():
    claims = [("suspect", "weapon", "knife")]
    reasons = override_reasons(claims, Flags(weapon_present=True), NEWBURY, robbery_snapshot(), 400)
    assert "new_weapon" in reasons
    assert "new_location" in reasons


def test_known_weapon_is_not_new():
    snapshot = IncidentSnapshot.build("inc-A", BOYLSTON, [("suspect", "weapon", "knife")], Flags(weapon_present=True))
    reasons = override_reasons([("suspect", "weapon", "knife")], Flags(weapon_present=True), BOYLSTON, snapshot, 400)
    assert reasons == []


def test_weapon_value_is_new_even_when_armed_was_flagged():
    reasons = override_reasons([("suspect", "weapon", "knife")], Flags(weapon_present=True), BOYLSTON,
                               robbery_snapshot(weapon_present=True), 400)
    assert reasons == ["new_weapon"]


def test_new_injury_and_injury_increase():
    crash = IncidentSnapshot.build("inc-C", BOYLSTON, [("vehicle", "vehicle_type", "suv")], Flags())
    reasons = override_reasons([("victim", "victim_condition", "not_moving")], Flags(injuries_reported=True), BOYLSTON, crash, 2000)
    assert reasons == ["new_injury"]

    hurt = IncidentSnapshot.build("inc-C", BOYLSTON, [("victim", "injury_count", "1")], Flags(injuries_reported=True))
    assert override_reasons([("victim", "injury_count", "3")], Flags(injuries_reported=True), BOYLSTON, hurt, 2000) == ["injury_increase"]
    assert override_reasons([("victim", "injury_count", "1")], Flags(injuries_reported=True), BOYLSTON, hurt, 2000) == []


def test_new_hazard_for_fire_and_for_trapped():
    crash = IncidentSnapshot.build("inc-C", BOYLSTON, [], Flags(injuries_reported=True))
    assert override_reasons([("vehicle", "hazard", "fire")], Flags(fire_or_smoke=True), BOYLSTON, crash, 2000) == ["new_hazard"]
    smoky = IncidentSnapshot.build("inc-F", BOYLSTON, [("scene", "hazard", "smoke")], Flags(fire_or_smoke=True))
    assert override_reasons([], Flags(fire_or_smoke=True), BOYLSTON, smoky, 600) == []
    assert override_reasons([], Flags(trapped=True), BOYLSTON, smoky, 600) == ["new_hazard"]


def test_queue_order_priority_then_oldest():
    def item(call_id, prio, seconds):
        return QueueItem(call_id=call_id, incident_id="i", received_at=T0 + timedelta(seconds=seconds), priority=prio)

    ordered = queue_order([item("a", 40, 10), item("b", 90, 50), item("c", 40, 5), item("d", 100, 99)])
    assert [i.call_id for i in ordered] == ["d", "b", "c", "a"]
