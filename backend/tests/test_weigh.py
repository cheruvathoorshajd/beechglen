"""Claim weighting and consensus (README -> "5. Weigh")."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.contracts import ValueShare
from app.pipeline.weigh import (
    ClaimEvidence,
    claim_weight,
    consensus,
    contradictions,
    is_contested,
    repeat_callers,
)

T0 = datetime(2026, 10, 24, 14, 0, tzinfo=timezone(timedelta(hours=-4)))


def ev(call_id, value, role, *, attribute="upper_clothing_color", subject="suspect", first_hand=True,
       status="verified", provisional=False, repeat=False, at=T0):
    return ClaimEvidence(
        claim_id=f"clm-{call_id}-{attribute}",
        call_id=call_id,
        subject=subject,
        attribute=attribute,
        value=value,
        first_hand=first_hand,
        status=status,
        provisional=provisional,
        caller_role=role,
        received_at=at,
        repeat_caller=repeat,
    )


def robbery_jackets():
    white = [ev("c01", "white", "victim")] + [ev(c, "white", "witness") for c in ("c02", "c04", "c06", "c08", "c11")]
    white.append(ev("c09", "white", "bystander"))
    black = [
        ev("c03", "black", "bystander"),
        ev("c05", "black", "unknown", first_hand=False),
        ev("c07", "black", "bystander", repeat=True),
    ]
    return white + black


def test_seven_white_versus_three_black_weighs_83_17_not_contested():
    [entry] = consensus(robbery_jackets(), T0)
    assert (entry.subject, entry.attribute) == ("suspect", "upper_clothing_color")
    white, black = entry.values
    assert white.value == "white" and white.share == pytest.approx(0.8333, abs=1e-3)
    assert black.value == "black" and black.share == pytest.approx(0.1667, abs=1e-3)
    assert (white.sources, black.sources) == (7, 3)
    assert (white.first_hand_sources, black.first_hand_sources) == (7, 2)
    assert entry.contested is False


def test_repeat_caller_is_every_later_call_from_the_same_hash():
    calls = [("c03", "rep-1", T0 + timedelta(seconds=70)), ("c05", "x", T0), ("c07", "rep-1", T0 + timedelta(seconds=190))]
    assert repeat_callers(calls) == {"c07"}


def test_weight_factors_multiply():
    assert claim_weight(ev("a", "white", "official"), T0) == pytest.approx(0.95)
    assert claim_weight(ev("a", "white", "child", first_hand=False), T0) == pytest.approx(0.35 * 0.5)
    assert claim_weight(ev("a", "white", "witness", status="pending_verification"), T0) == pytest.approx(0.65 * 0.6)
    assert claim_weight(ev("a", "white", "witness", repeat=True), T0) == pytest.approx(0.65 * 0.3)
    assert claim_weight(ev("a", "white", "witness", status="rejected"), T0) == 0.0


def test_recency_decays_only_mutable_attributes():
    now = T0 + timedelta(minutes=15)
    old_direction = ev("a", "hynes station", "witness", attribute="direction_of_travel", at=T0)
    assert claim_weight(old_direction, now) == pytest.approx(0.65 * math.exp(-1), rel=1e-4)
    old_color = ev("a", "white", "witness", at=T0)
    assert claim_weight(old_color, now) == pytest.approx(0.65)


def test_rejected_and_provisional_claims_are_excluded_from_consensus():
    evidence = [
        ev("a", "white", "witness"),
        ev("b", "black", "witness", status="rejected"),
        ev("c", "black", "witness", provisional=True),
    ]
    [entry] = consensus(evidence, T0)
    assert [v.value for v in entry.values] == ["white"]
    assert entry.values[0].share == 1.0


def test_contested_rule():
    def shares(*values):
        return [ValueShare(value=str(i), share=s, sources=1, first_hand_sources=1) for i, s in enumerate(values)]

    assert is_contested(shares(0.6, 0.4))
    assert is_contested(shares(0.65, 0.20, 0.15))
    assert not is_contested(shares(0.70, 0.30))
    assert not is_contested(shares(0.69, 0.19, 0.12))
    assert not is_contested(shares(1.0))


def test_minority_values_stay_visible_in_order():
    evidence = [ev("a", "silver", "witness"), ev("b", "silver", "witness"), ev("c", "white", "witness")]
    [entry] = consensus(evidence, T0)
    assert [v.value for v in entry.values] == ["silver", "white"]


def test_contradictions_list_values_and_cross_call_edges():
    found, pairs = contradictions(robbery_jackets(), T0)
    assert len(found) == 1
    assert found[0].values == ["white", "black"]
    assert len(pairs) == 7 * 3


def test_same_call_two_values_is_not_a_contradiction():
    evidence = [ev("a", "white", "witness"), replace(ev("a", "gray", "witness"), claim_id="clm-a-2")]
    found, pairs = contradictions(evidence, T0)
    assert found == [] and pairs == []
