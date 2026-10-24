"""Scenario data follows the KIRO_PROMPTS.md 0.3 generation rules exactly.

Downstream tests and the evaluation depend on these facts, so they are locked
here rather than trusted.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest

from app.contracts import CallIn
from app.geo import haversine_m
from app.paths import SCENARIO_DIR


def load(name: str) -> dict:
    return json.loads((SCENARIO_DIR / f"{name}.json").read_text(encoding="utf-8"))


def by_id(scenario: dict) -> dict[str, dict]:
    return {call["id"]: call for call in scenario["calls"]}


def words(text: str) -> str:
    return text.lower()


@pytest.mark.parametrize("name", ["mass_ave_robbery", "pike_crash", "washington_st"])
def test_every_call_is_a_valid_call_in(name):
    scenario = load(name)
    assert scenario["scenario_id"] == name
    start = datetime.fromisoformat(scenario["start_time"])
    assert start.utcoffset().total_seconds() == -4 * 3600
    for call in scenario["calls"]:
        payload = {k: v for k, v in call.items() if k not in ("id", "t_offset_s")}
        CallIn.model_validate({**payload, "received_at": start, "scenario_id": name})
        sentences = [s for s in re.split(r"[.!?]+\s*", call["transcript"]) if s.strip()]
        assert 1 <= len(sentences) <= 5, call["id"]
    offsets = [call["t_offset_s"] for call in scenario["calls"]]
    assert offsets == sorted(offsets)


def test_mass_ave_robbery_rules():
    scenario = load("mass_ave_robbery")
    calls = by_id(scenario)
    assert scenario["start_time"] == "2026-10-24T14:00:00-04:00"
    assert [c["t_offset_s"] for c in scenario["calls"]] == [0, 40, 70, 100, 130, 160, 190, 220, 260, 360, 400, 720]

    white = ["c01", "c02", "c06", "c08", "c09", "c11"]
    black = ["c03", "c05", "c07"]
    for cid in white:
        assert "white jacket" in words(calls[cid]["transcript"]) and "black" not in words(calls[cid]["transcript"]), cid
    assert "chaqueta blanca" in calls["c04"]["transcript"]
    for cid in black:
        assert "black jacket" in words(calls[cid]["transcript"]) and "white" not in words(calls[cid]["transcript"]), cid
    for cid in ("c10", "c12"):
        text = words(calls[cid]["transcript"])
        assert "jacket" not in text and "white" not in text and "black" not in text, cid

    assert calls["c03"]["caller_hash"] == calls["c07"]["caller_hash"] == "rep-1"
    others = [c["caller_hash"] for cid, c in calls.items() if cid not in ("c03", "c07")]
    assert len(set(others)) == len(others)
    assert "neighbor" in words(calls["c05"]["transcript"])
    assert calls["c01"]["caller_role_hint"] == "victim"
    assert calls["c05"]["caller_role_hint"] == "unknown"

    anchor = (42.3470, -71.0874)
    for cid in ("c01", "c02", "c03", "c04", "c05", "c06", "c07", "c08", "c09", "c11"):
        call = calls[cid]
        assert "boylston" in words(call["transcript"]), cid
        assert abs(call["device_lat"] - anchor[0]) <= 0.0003 and abs(call["device_lng"] - anchor[1]) <= 0.0003, cid
    assert (calls["c10"]["device_lat"], calls["c10"]["device_lng"]) == (42.3485, -71.0878)
    assert (calls["c12"]["device_lat"], calls["c12"]["device_lng"]) == (42.3446, -71.0880)
    assert "knife" in words(calls["c10"]["transcript"]) and "newbury" in words(calls["c10"]["transcript"])
    assert "trapped" in words(calls["c12"]["transcript"]) and "robbery" not in words(calls["c12"]["transcript"])

    assert {cid for cid, c in calls.items() if c["truth_new_info"]} == {"c01", "c10", "c12"}
    assert {cid for cid, c in calls.items() if c["truth_incident"] == "B"} == {"c12"}
    assert all(c["psap_id"] == "boston-ecc" for c in calls.values())


def test_pike_crash_rules():
    scenario = load("pike_crash")
    calls = by_id(scenario)
    assert scenario["start_time"] == "2026-10-24T08:00:00-04:00"
    assert [c["t_offset_s"] for c in scenario["calls"]] == [0, 30, 55, 80, 110, 140, 170, 200, 240, 300, 330, 380]
    assert all(c["truth_incident"] == "C" and c["psap_id"] == "msp-pike" for c in calls.values())

    for cid in ("p01", "p03", "p05", "p07", "p08", "p11"):
        assert "silver suv" in words(calls[cid]["transcript"]), cid
    for cid in ("p02", "p04", "p12"):
        assert "white suv" in words(calls[cid]["transcript"]), cid
    assert "suv branco" in words(calls["p06"]["transcript"])
    for cid in ("p09", "p10"):
        text = words(calls[cid]["transcript"])
        assert "silver" not in text and "white" not in text, cid

    assert "pike eastbound right before exit 63" in words(calls["p01"]["transcript"])
    assert "near old exit 8 in palmer" in words(calls["p02"]["transcript"])
    assert "around mile marker 62" in words(calls["p04"]["transcript"])
    assert "mass pike near palmer" in words(calls["p07"]["transcript"])
    assert "the turnpike eastbound" in words(calls["p08"]["transcript"])
    assert calls["p05"]["channel"] == "text"
    assert calls["p07"]["transferred_from"] == "palmer-local"
    assert "not moving" in words(calls["p03"]["transcript"]) or "isn't moving" in words(calls["p03"]["transcript"])
    assert "on fire" in words(calls["p10"]["transcript"])

    before_p03 = [calls[c]["transcript"] for c in ("p01", "p02")]
    assert not any(re.search(r"hurt|injur|bleed|moving|unconscious", words(t)) for t in before_p03)
    before_p10 = [c["transcript"] for c in scenario["calls"] if c["t_offset_s"] < 300]
    assert not any(re.search(r"fire|smoke|flame", words(t)) for t in before_p10)

    anchor = (42.1730, -72.3280)
    for cid, call in calls.items():
        if cid in ("p06", "p09"):
            assert call["device_lat"] is None and call["device_lng"] is None
        else:
            assert haversine_m(anchor, (call["device_lat"], call["device_lng"])) <= 500, cid
    assert {cid for cid, c in calls.items() if c["truth_new_info"]} == {"p01", "p03", "p10"}


def test_washington_st_rules():
    scenario = load("washington_st")
    calls = by_id(scenario)
    assert scenario["start_time"] == "2026-10-24T22:00:00-04:00"
    expected = {
        "w01": ("boston-ecc", (42.3555, -71.0605), "D"),
        "w02": ("brookline-local", (42.3326, -71.1166), "E"),
        "w03": ("boston-ecc", None, "D"),
        "w04": ("boston-ecc", (42.3555, -71.0605), "D"),
    }
    for cid, (psap, device, truth) in expected.items():
        call = calls[cid]
        assert call["psap_id"] == psap and call["truth_incident"] == truth and call["truth_new_info"] is True
        assert "washington" in words(call["transcript"])
        assert not re.search(r"\b(boston|brookline|somerville)\b", words(call["transcript"])), cid
        if device is None:
            assert call["device_lat"] is None and call["device_lng"] is None
        else:
            assert abs(call["device_lat"] - device[0]) <= 0.0003 and abs(call["device_lng"] - device[1]) <= 0.0003
    assert "bottle" in words(calls["w03"]["transcript"])
    assert "bleeding" in words(calls["w04"]["transcript"])
    assert "downtown crossing" in words(calls["w04"]["transcript"])
