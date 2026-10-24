"""End-to-end pipeline through the LangGraph flow, with hand-built extractions.

Extraction is faked (no LLM, no cache); quote grounding, locate, link, weigh,
priority and dispatch are the real implementations.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.context import AppContext
from app.contracts import CallIn, ExtractedClaim, Extraction, Flags, LocationMention
from app.flow.runner import LinkActionError
from app.graph.store import RelKind

ROBBERY_T0 = datetime(2026, 10, 24, 14, 0, tzinfo=timezone(timedelta(hours=-4)))
PIKE_T0 = datetime(2026, 10, 24, 8, 0, tzinfo=timezone(timedelta(hours=-4)))
WASH_T0 = datetime(2026, 10, 24, 22, 0, tzinfo=timezone(timedelta(hours=-4)))
BOYLSTON = (42.3470, -71.0874)
NEWBURY = (42.3485, -71.0878)
WESTLAND = (42.3446, -71.0880)
DOWNTOWN = (42.3555, -71.0605)
BROOKLINE = (42.3326, -71.1166)
EXIT_63 = (42.1730, -72.3280)


def claim(subject, attribute, value, quote, first_hand=True):
    return ExtractedClaim(subject=subject, attribute=attribute, value=value, quote=quote, first_hand=first_hand)


class FakeExtractor:
    """Maps a transcript to a prepared extraction; unknown transcripts raise."""

    def __init__(self):
        self.by_transcript: dict[str, Extraction] = {}

    def add(self, transcript: str, **fields) -> str:
        self.by_transcript[transcript] = Extraction(**fields)
        return transcript

    def __call__(self, call: CallIn) -> Extraction:
        return self.by_transcript[call.transcript]


def call(transcript, t0, seconds, *, caller, device=None, psap="boston-ecc", transferred_from=None):
    return CallIn(
        transcript=transcript,
        received_at=t0 + timedelta(seconds=seconds),
        caller_hash=caller,
        device_lat=device[0] if device else None,
        device_lng=device[1] if device else None,
        psap_id=psap,
        transferred_from=transferred_from,
    )


@pytest.fixture
def robbery():
    fake = FakeExtractor()
    store_at = LocationMention(street="Mass Ave", cross_street="Boylston")
    texts = {
        "c1": fake.add(
            "I'm the clerk at Mass Ave and Boylston. A man in a white jacket robbed us and ran toward Hynes station.",
            incident_type="robbery", caller_role="victim", location=store_at,
            claims=[claim("suspect", "upper_clothing_color", "white", "white jacket"),
                    claim("suspect", "direction_of_travel", "hynes station", "ran toward Hynes station")],
            summary="Robbery at the store",
        ),
        "c2": fake.add(
            "I'm at Mass Ave and Boylston. He had a black jacket.",
            incident_type="robbery", caller_role="bystander", location=store_at,
            claims=[claim("suspect", "upper_clothing_color", "black", "black jacket")],
        ),
        "c3": fake.add(
            "I'm at Mass Ave and Boylston. I saw the man in the white jacket.",
            incident_type="robbery", caller_role="witness", location=store_at,
            claims=[claim("suspect", "upper_clothing_color", "white", "white jacket")],
        ),
        "knife": fake.add(
            "I'm at Mass Ave and Newbury. The guy from the store just pulled a knife on someone.",
            incident_type="robbery", caller_role="witness", flags=Flags(weapon_present=True),
            location=LocationMention(street="Mass Ave", cross_street="Newbury"),
            claims=[claim("suspect", "weapon", "knife", "pulled a knife")],
        ),
        "fire": fake.add(
            "Smoke is pouring out of a window on Westland Ave and people are trapped.",
            incident_type="fire", caller_role="witness", flags=Flags(fire_or_smoke=True, trapped=True),
            location=LocationMention(street="Westland Ave"),
            claims=[claim("scene", "hazard", "smoke", "Smoke is pouring")],
        ),
    }
    return AppContext.create(extract=fake), texts


def test_duplicates_link_and_sink_while_minority_stays_visible(robbery):
    ctx, texts = robbery
    r1 = ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    r2 = ctx.runner.process_call(call(texts["c2"], ROBBERY_T0, 40, caller="b", device=BOYLSTON))
    r3 = ctx.runner.process_call(call(texts["c3"], ROBBERY_T0, 70, caller="c", device=BOYLSTON))

    assert r1.link.band == "new" and r1.queue_item.override_reasons == ["new_incident"]
    assert r1.queue_item.priority == 80
    assert r2.link.band == r3.link.band == "auto"
    assert r1.incident_id == r2.incident_id == r3.incident_id
    assert r3.queue_item.novelty == 0.0 and r3.queue_item.priority <= 5
    assert r2.queue_item.priority > r3.queue_item.priority  # black jacket was new information

    assert [item.call_id for item in ctx.views.queue()] == [r1.link.call_id, r2.link.call_id, r3.link.call_id]

    detail = ctx.views.incident_detail(r1.incident_id)
    jacket = next(c for c in detail.consensus if c.attribute == "upper_clothing_color")
    assert [v.value for v in jacket.values] == ["white", "black"]
    assert detail.contradictions[0].values == ["white", "black"]
    assert detail.incident.call_count == 3
    assert detail.dispatch.agencies == ["Boston Police"]
    assert detail.incident.dispatch_ready_at == ROBBERY_T0
    assert any("hynes station" in lead.description and lead.status == "suggested" for lead in detail.leads)
    assert [e.action for e in ctx.audit.events()] == ["link.decided"] * 3
    assert all(c.weight > 0 for c in r3.claims)


def test_new_weapon_escalates_and_is_audited(robbery):
    ctx, texts = robbery
    first = ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    knife = ctx.runner.process_call(call(texts["knife"], ROBBERY_T0, 360, caller="k", device=NEWBURY))

    assert knife.incident_id == first.incident_id
    assert knife.link.band in ("auto", "suggest")
    assert "new_weapon" in knife.queue_item.override_reasons
    assert knife.queue_item.new_info and knife.queue_item.priority >= 90
    overrides = [e for e in ctx.audit.events() if e.action == "priority.override"]
    assert overrides and "new_weapon" in overrides[0].details["reasons"]


def test_fire_a_block_away_is_a_new_incident_at_the_top(robbery):
    ctx, texts = robbery
    ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    fire = ctx.runner.process_call(call(texts["fire"], ROBBERY_T0, 720, caller="f", device=WESTLAND))

    assert fire.link.band == "new"
    assert "incompatible_type_cap" in fire.link.gates
    assert fire.link.p_same <= 0.49
    assert fire.queue_item.priority == 100
    assert ctx.views.queue()[0].call_id == fire.link.call_id
    package = ctx.views.incident_detail(fire.incident_id).dispatch
    assert package.rule_id == "fire_trapped"
    assert package.agencies == ["Boston Police", "Boston Fire", "Boston EMS"]


def test_split_creates_a_new_incident_and_recomputes_both(robbery):
    ctx, texts = robbery
    r1 = ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    r2 = ctx.runner.process_call(call(texts["c2"], ROBBERY_T0, 40, caller="b", device=BOYLSTON))

    split = ctx.runner.split_call(r2.link.call_id)
    assert split.incident_id != r1.incident_id
    assert split.link.band == "new" and split.link.decided_by == "operator"
    assert "operator_split" in split.link.gates
    assert split.queue_item.override_reasons == ["new_incident"]

    original = ctx.views.incident_detail(r1.incident_id)
    jacket = next(c for c in original.consensus if c.attribute == "upper_clothing_color")
    assert [v.value for v in jacket.values] == ["white"]
    assert original.contradictions == []
    assert ctx.store.edge_counts().get(str(RelKind.CONTRADICTS), 0) == 0
    assert ctx.views.incident_detail(split.incident_id).incident.call_count == 1
    assert [e.action for e in ctx.audit.events()][-1] == "link.split"

    with pytest.raises(LinkActionError):
        ctx.runner.split_call(r2.link.call_id)
    with pytest.raises(LinkActionError):
        ctx.runner.confirm_link(r1.link.call_id)


def test_ambiguous_street_is_suggested_then_confirmed():
    fake = FakeExtractor()
    washington = LocationMention(street="Washington Street")
    w1 = fake.add("Two men are fighting on Washington Street.", incident_type="assault", location=washington,
                  claims=[claim("scene", "people_count", "2", "Two men")])
    w2 = fake.add("There's a fight outside a bar on Washington Street.", incident_type="assault", location=washington)
    w3 = fake.add("A fight on Washington Street. One guy has a bottle.", incident_type="assault",
                  location=washington, caller_role="bystander", flags=Flags(weapon_present=True),
                  claims=[claim("suspect", "weapon", "bottle", "has a bottle")])
    ctx = AppContext.create(extract=fake)

    d = ctx.runner.process_call(call(w1, WASH_T0, 0, caller="1", device=DOWNTOWN, psap="boston-ecc"))
    e = ctx.runner.process_call(call(w2, WASH_T0, 60, caller="2", device=BROOKLINE, psap="brookline-local"))
    s = ctx.runner.process_call(call(w3, WASH_T0, 120, caller="3", psap="boston-ecc"))

    assert d.incident_id != e.incident_id
    assert s.link.band == "suggest" and s.incident_id == d.incident_id
    assert "low_location_confidence" in s.link.gates
    assert ctx.views.call_detail(s.link.call_id).location.ambiguous
    assert all(c.provisional for c in s.claims)
    assert "new_weapon" in s.queue_item.override_reasons
    assert not any(c.attribute == "weapon" for c in ctx.views.incident_detail(d.incident_id).consensus)

    confirmed = ctx.runner.confirm_link(s.link.call_id)
    assert confirmed.link.band == "confirmed" and confirmed.link.decided_by == "operator"
    assert confirmed.queue_item.band == "confirmed"
    assert not any(c.provisional for c in confirmed.claims)
    assert any(c.attribute == "weapon" for c in ctx.views.incident_detail(d.incident_id).consensus)
    assert ctx.audit.events()[-1].action == "link.confirmed"
    assert ctx.views.metrics().bands == {"auto": 0, "suggest": 0, "new": 2, "confirmed": 1}


def test_pike_exits_transfer_injury_and_state_police():
    fake = FakeExtractor()
    p1 = fake.add("Crash on the Pike eastbound right before exit 63. A silver SUV and a red pickup collided.",
                  incident_type="vehicle_crash",
                  location=LocationMention(highway_route="the Pike", highway_direction="EB", highway_exit="63"),
                  claims=[claim("vehicle", "vehicle_color", "silver", "silver SUV"),
                          claim("vehicle", "vehicle_type", "suv", "silver SUV"),
                          claim("vehicle_2", "vehicle_type", "pickup", "red pickup")])
    p2 = fake.add("I'm near old exit 8 in Palmer. A white SUV and a red pickup crashed.",
                  incident_type="vehicle_crash",
                  location=LocationMention(highway_route="Pike", highway_exit="8", exit_is_old=True, town="Palmer"),
                  claims=[claim("vehicle", "vehicle_color", "white", "white SUV"),
                          claim("vehicle", "vehicle_type", "suv", "white SUV")])
    p3 = fake.add("On the Pike near Palmer. The pickup driver isn't moving.", incident_type="vehicle_crash",
                  flags=Flags(injuries_reported=True),
                  location=LocationMention(highway_route="Pike", town="Palmer"),
                  claims=[claim("victim", "victim_condition", "not_moving", "isn't moving")])
    ctx = AppContext.create(extract=fake)

    r1 = ctx.runner.process_call(call(p1, PIKE_T0, 0, caller="1", device=EXIT_63, psap="msp-pike"))
    r2 = ctx.runner.process_call(call(p2, PIKE_T0, 30, caller="2", device=EXIT_63, psap="msp-pike",
                                      transferred_from="palmer-local"))
    r3 = ctx.runner.process_call(call(p3, PIKE_T0, 55, caller="3", device=EXIT_63, psap="msp-pike"))

    assert r1.incident_id == r2.incident_id == r3.incident_id
    assert r3.queue_item.override_reasons == ["new_injury"]
    detail = ctx.views.incident_detail(r1.incident_id)
    assert [(t.from_psap, t.to_psap) for t in detail.transfers] == [("palmer-local", "msp-pike")]
    assert detail.dispatch.rule_id == "crash_highway_injuries"
    assert detail.dispatch.recommended_units == ["2 EMS", "1 Fire", "State Police"]
    assert "Massachusetts State Police" in detail.dispatch.agencies
    color = next(c for c in detail.consensus if (c.subject, c.attribute) == ("vehicle", "vehicle_color"))
    assert {v.value for v in color.values} == {"silver", "white"} and color.contested
    assert detail.incident.dispatch_ready_at == PIKE_T0


def test_extraction_failure_still_enters_the_graph():
    ctx = AppContext.create(extract=FakeExtractor())  # every transcript is unknown -> raises
    result = ctx.runner.process_call(
        CallIn(transcript="Help, something is happening near the park.", received_at=datetime(2026, 10, 24, 12, 0),
               caller_hash="x")
    )
    assert result.link.band == "new"
    assert ctx.views.call_detail(result.link.call_id).extraction.incident_type == "other"
    assert len(ctx.views.queue()) == 1
    assert ctx.views.metrics().calls == 1


def test_reset_clears_graph_and_audit(robbery):
    ctx, texts = robbery
    ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    ctx.reset()
    assert ctx.views.queue() == [] and ctx.views.incidents() == [] and ctx.audit.events() == []
    again = ctx.runner.process_call(call(texts["c1"], ROBBERY_T0, 0, caller="a", device=BOYLSTON))
    assert again.link.call_id == "c-0001"
