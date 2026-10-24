"""Scenario acceptance tests (KIRO_PROMPTS.md I4, README "Demo scenarios").

Replays every scenario in-process with DEMO_MODE=offline, so only cached
extractions are used. If a failure comes from a cached extraction, fix the
cache entry (playbook I2) rather than the pipeline.
"""

from __future__ import annotations

import pytest

from app.paths import EXTRACTION_CACHE_DIR, SCENARIO_DIR
from app.pipeline.extract import cache_path
from app.sim.evaluation import ScenarioRun, run_scenario
from app.sim.replay import list_scenarios, load_scenario

pytestmark = pytest.mark.scenario


def _missing_cache() -> list[str]:
    return [
        f"{scenario_id}/{item.scenario_call_id}"
        for scenario_id in list_scenarios(SCENARIO_DIR)
        for item in load_scenario(scenario_id).calls
        if not cache_path(item.call.transcript, EXTRACTION_CACHE_DIR).is_file()
    ]


@pytest.fixture(scope="module", autouse=True)
def _require_cache():
    missing = _missing_cache()
    if len(missing) == sum(len(load_scenario(s).calls) for s in list_scenarios(SCENARIO_DIR)):
        pytest.skip("extraction cache is empty: run scripts/precompute_extractions.py")
    assert not missing, f"calls without a cached extraction: {missing}"


def replay(scenario_id: str) -> ScenarioRun:
    return run_scenario(scenario_id)


def consensus_entry(detail, subject, attribute):
    return next((c for c in detail.consensus if (c.subject, c.attribute) == (subject, attribute)), None)


def test_mass_ave_robbery():
    run = replay("mass_ave_robbery")
    calls = run.by_scenario_id()
    robbery = calls["c01"].incident_id
    assert {calls[f"c{i:02d}"].incident_id for i in range(1, 12)} == {robbery}

    detail = run.ctx.views.incident_detail(robbery)
    colors = consensus_entry(detail, "suspect", "upper_clothing_color")
    shares = {v.value: v.share for v in colors.values}
    assert 0.75 <= shares["white"] <= 0.90, shares
    assert "black" in shares
    assert colors.contested is False

    knife = calls["c10"]
    assert knife.new_info and "new_weapon" in knife.override_reasons
    assert knife.priority >= 90

    fire = calls["c12"]
    assert fire.incident_id != robbery and fire.band == "new"
    assert fire.priority == 100
    assert run.ctx.views.queue()[0].call_id == fire.call_id
    assert "incompatible_type_cap" in run.ctx.views.explain(fire.call_id).gates


def test_pike_crash():
    run = replay("pike_crash")
    calls = run.by_scenario_id()
    incident = calls["p01"].incident_id
    assert {record.incident_id for record in run.records} == {incident}

    detail = run.ctx.views.incident_detail(incident)
    assert any("State Police" in agency for agency in detail.dispatch.agencies)
    assert [(t.from_psap, t.to_psap) for t in detail.transfers] == [("palmer-local", "msp-pike")]

    suv_subjects = [
        c.subject for c in detail.consensus
        if c.attribute == "vehicle_type" and c.values and c.values[0].value == "suv"
    ]
    assert suv_subjects, "no vehicle subject is an SUV"
    color = consensus_entry(detail, suv_subjects[0], "vehicle_color")
    assert {"silver", "white"} <= {v.value for v in color.values}

    assert "new_injury" in calls["p03"].override_reasons
    assert "new_hazard" in calls["p10"].override_reasons


def test_washington_st():
    run = replay("washington_st")
    calls = run.by_scenario_id()
    boston, brookline = calls["w01"].incident_id, calls["w02"].incident_id
    assert boston != brookline

    w03 = calls["w03"]
    assert w03.band == "suggest" and w03.incident_id == boston
    assert run.ctx.views.call_detail(w03.call_id).location.ambiguous
    ask = run.ctx.assist.ask_next(run.ctx.views.call_detail(w03.call_id), run.ctx.views.incident_detail(boston))
    assert "Which town are you in?" in ask.questions

    w04 = calls["w04"]
    assert w04.incident_id == boston and "new_injury" in w04.override_reasons
