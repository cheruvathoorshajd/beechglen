"""Extraction: cache, demo modes, fallback and fail-open parsing (README -> "1. Extract")."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.contracts import CallIn, Extraction
from app.pipeline.extract import Extractor, cache_path, save_cached

T0 = datetime(2026, 10, 24, 14, 0, tzinfo=timezone(timedelta(hours=-4)))
TRANSCRIPT = (
    "I'm at Mass Ave and Boylston. A man in a white jacket just robbed the store and he ran toward "
    "Hynes station with the cash in a bag."
)
RAW = {
    "language": "en",
    "incident_type": "Robbery",
    "caller_role": "witness",
    "flags": {"weapon_present": False, "mood": "scared"},
    "location": {"street": "Mass Ave", "cross_street": "Boylston", "raw": "Mass Ave and Boylston"},
    "claims": [
        {"subject": "suspect", "attribute": "upper_clothing_color", "value": "White ", "quote": "white jacket",
         "first_hand": True, "confidence": 0.9},
        {"subject": "suspect", "attribute": "upper_clothing_color", "value": "white", "quote": "white jacket",
         "first_hand": True, "confidence": 0.9},
        {"subject": "suspect", "attribute": "tattoo", "value": "rose", "quote": "rose", "first_hand": True, "confidence": 1},
    ],
    "summary": "Robbery at Mass Ave and Boylston; suspect fled toward Hynes.",
    "reasoning": "not part of the contract",
}


def make_call(transcript=TRANSCRIPT, hint=None, channel="voice"):
    return CallIn(transcript=transcript, channel=channel, received_at=T0, caller_hash="h1", caller_role_hint=hint)


def settings(mode="cache_first", key="test-key"):
    return lambda: Settings(_env_file=None, demo_mode=mode, anthropic_api_key=key)


def never_called(**kwargs):
    pytest.fail(f"model must not be called: {kwargs.get('tool_name')}")


class FakeCaller:
    def __init__(self, result):
        self.result = result
        self.requests = []

    def __call__(self, **kwargs):
        self.requests.append(kwargs)
        return self.result


def test_cache_hit_skips_the_model(tmp_path):
    call = make_call()
    save_cached(cache_path(call.transcript, tmp_path), call, Extraction(incident_type="robbery", summary="cached"), "m")
    extraction = Extractor(tool_caller=never_called, settings=settings(), cache_dir=tmp_path)(call)
    assert extraction.incident_type == "robbery"
    assert extraction.summary == "cached"


def test_caller_role_hint_overrides_extracted_role(tmp_path):
    call = make_call(hint="victim")
    save_cached(cache_path(call.transcript, tmp_path), call, Extraction(caller_role="witness"), "m")
    assert Extractor(tool_caller=never_called, settings=settings(), cache_dir=tmp_path)(call).caller_role == "victim"


def test_offline_cache_miss_returns_minimal_extraction(tmp_path):
    extraction = Extractor(tool_caller=never_called, settings=settings("offline"), cache_dir=tmp_path)(make_call())
    assert extraction.incident_type == "other"
    assert extraction.claims == []
    assert extraction.summary == " ".join(TRANSCRIPT.split()[:20])
    assert list(tmp_path.iterdir()) == []


def test_missing_api_key_never_calls_the_model(tmp_path):
    extraction = Extractor(tool_caller=never_called, settings=settings(key=None), cache_dir=tmp_path)(make_call())
    assert extraction.incident_type == "other"


def test_cache_first_miss_calls_model_sanitizes_and_caches(tmp_path):
    caller = FakeCaller(RAW)
    call = make_call()
    extraction = Extractor(tool_caller=caller, settings=settings(), cache_dir=tmp_path)(call)

    request = caller.requests[0]
    assert request["model"] == "claude-sonnet-5-5"
    assert request["tool_name"] == "record_extraction"
    assert request["user"].startswith("Channel: voice\nTranscript:\n<<<\n")
    assert TRANSCRIPT in request["user"]

    assert extraction.incident_type == "robbery"
    assert extraction.location.cross_street == "Boylston"
    assert [(c.attribute, c.value) for c in extraction.claims] == [("upper_clothing_color", "white")]

    payload = json.loads(cache_path(call.transcript, tmp_path).read_text(encoding="utf-8"))
    assert payload["transcript"] == TRANSCRIPT
    assert payload["extraction"]["incident_type"] == "robbery"

    again = Extractor(tool_caller=never_called, settings=settings(), cache_dir=tmp_path)(call)
    assert again == extraction


def test_model_failure_falls_back_and_is_not_cached(tmp_path):
    extraction = Extractor(tool_caller=FakeCaller(None), settings=settings(), cache_dir=tmp_path)(make_call())
    assert extraction.incident_type == "other"
    assert list(tmp_path.iterdir()) == []


def test_unusable_model_output_falls_back(tmp_path):
    extraction = Extractor(tool_caller=FakeCaller(["not", "an", "object"]), settings=settings(), cache_dir=tmp_path)(make_call())
    assert extraction.incident_type == "other"


def test_corrupt_cache_file_is_ignored(tmp_path):
    call = make_call()
    cache_path(call.transcript, tmp_path).write_text("{ not json", encoding="utf-8")
    extraction = Extractor(tool_caller=never_called, settings=settings("offline"), cache_dir=tmp_path)(call)
    assert extraction.incident_type == "other"


def test_precompute_reports_each_outcome(tmp_path):
    call = make_call()
    assert Extractor(tool_caller=FakeCaller(None), settings=settings(), cache_dir=tmp_path).precompute(call) == "failed"
    assert Extractor(tool_caller=FakeCaller(RAW), settings=settings(), cache_dir=tmp_path).precompute(call) == "extracted"
    assert Extractor(tool_caller=never_called, settings=settings(), cache_dir=tmp_path).precompute(call) == "cached"
