"""frontend/src/mocks/*.json must validate against the API contracts (KIRO_PROMPTS.md 0.7)."""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter

from app.contracts import (
    AskNext,
    Briefing,
    CallDetail,
    IncidentDetail,
    IncidentSummary,
    LinkDecision,
    Metrics,
    QueueItem,
    RuntimeSettings,
    SimStatus,
)
from app.paths import REPO_ROOT

MOCKS = REPO_ROOT / "frontend" / "src" / "mocks"
SHAPES = {
    "queue": list[QueueItem],
    "incidents": list[IncidentSummary],
    "incident": IncidentDetail,
    "call": CallDetail,
    "explain": LinkDecision,
    "ask-next": AskNext,
    "briefing": Briefing,
    "metrics": Metrics,
    "settings": RuntimeSettings,
    "sim-status": SimStatus,
}


def load(name):
    return json.loads((MOCKS / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(SHAPES))
def test_mock_matches_contract(name):
    TypeAdapter(SHAPES[name]).validate_python(load(name))


def test_mocks_cover_what_the_console_shows():
    queue = TypeAdapter(list[QueueItem]).validate_python(load("queue"))
    assert len(queue) == 8
    assert {item.band for item in queue} == {"auto", "suggest", "new", "confirmed"}
    assert any("new_weapon" in item.override_reasons for item in queue)
    assert {"es", "pt"} <= {item.language for item in queue}

    detail = IncidentDetail.model_validate(load("incident"))
    jacket = next(c for c in detail.consensus if c.attribute == "upper_clothing_color")
    assert [(v.value, round(v.share, 2)) for v in jacket.values] == [("white", 0.83), ("black", 0.17)]
    assert any(c.contested for c in detail.consensus)
    assert detail.contradictions and detail.transfers and len(detail.leads) >= 2
    assert detail.dispatch.recommended_units
