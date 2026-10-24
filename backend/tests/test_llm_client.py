"""Claude client wrapper: per-model request settings and fail-open behaviour."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import client as client_module
from app.llm.client import build_request, call_tool, model_profile, parse_tool_input

SCHEMA = {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"], "additionalProperties": False}


def request_for(model):
    return build_request(
        model=model,
        system="s",
        user="u",
        tool_name="record_x",
        tool_description="d",
        input_schema=SCHEMA,
    )


@pytest.mark.parametrize(
    ("model", "temperature", "forced", "thinking"),
    [
        ("claude-sonnet-5-5", False, False, True),
        ("claude-haiku-5-5", False, True, False),
        ("claude-opus-5-5", False, False, False),
        ("claude-sonnet-4-5", True, True, False),
        ("claude-haiku-4-5-20251001", True, True, False),
    ],
)
def test_model_profiles(model, temperature, forced, thinking):
    profile = model_profile(model)
    assert profile.accepts_temperature is temperature
    assert profile.accepts_forced_tool is forced
    assert (profile.thinking is not None) is thinking


def test_sonnet_5_5_request_uses_auto_strict_tool_and_no_sampling():
    request = request_for("claude-sonnet-5-5")
    assert request["tool_choice"] == {"type": "auto"}
    assert request["tools"][0]["strict"] is True
    assert request["thinking"] == {"type": "between_tools"}
    assert "temperature" not in request


def test_haiku_5_5_request_forces_the_tool_without_temperature():
    request = request_for("claude-haiku-5-5")
    assert request["tool_choice"] == {"type": "tool", "name": "record_x"}
    assert "temperature" not in request
    assert "thinking" not in request


def test_older_models_get_temperature_zero_and_forced_tool():
    request = request_for("claude-sonnet-4-5")
    assert request["temperature"] == 0
    assert request["tool_choice"] == {"type": "tool", "name": "record_x"}


def block(**fields):
    return SimpleNamespace(**fields)


def test_parse_selects_tool_block_by_type_not_position():
    response = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            block(type="thinking", thinking=""),
            block(type="text", text="calling"),
            block(type="tool_use", name="record_x", input={"x": "1"}),
        ],
    )
    assert parse_tool_input(response, "record_x") == {"x": "1"}


def test_parse_rejects_refusals_and_missing_tool():
    refusal = SimpleNamespace(stop_reason="refusal", content=[block(type="tool_use", name="record_x", input={})])
    assert parse_tool_input(refusal, "record_x") is None
    text_only = SimpleNamespace(stop_reason="end_turn", content=[block(type="text", text="no tool")])
    assert parse_tool_input(text_only, "record_x") is None


def offline_settings(**overrides):
    values = {"anthropic_api_key": None, "demo_mode": "cache_first"}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_call_tool_without_key_returns_none_without_calling_the_sdk(monkeypatch):
    monkeypatch.setattr(client_module, "_client", lambda *a: pytest.fail("SDK must not be called"))
    result = call_tool(
        model="claude-haiku-5-5", system="s", user="u", tool_name="record_x",
        tool_description="d", input_schema=SCHEMA, settings=offline_settings(),
    )
    assert result is None


def test_call_tool_offline_mode_never_calls_the_sdk(monkeypatch):
    monkeypatch.setattr(client_module, "_client", lambda *a: pytest.fail("SDK must not be called"))
    settings = offline_settings(anthropic_api_key="test-key", demo_mode="offline")
    result = call_tool(
        model="claude-haiku-5-5", system="s", user="u", tool_name="record_x",
        tool_description="d", input_schema=SCHEMA, settings=settings,
    )
    assert result is None


class FakeMessages:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def test_call_tool_returns_tool_input(monkeypatch):
    response = SimpleNamespace(stop_reason="tool_use", content=[block(type="tool_use", name="record_x", input={"x": "ok"})])
    messages = FakeMessages(response=response)
    monkeypatch.setattr(client_module, "_client", lambda *a: SimpleNamespace(messages=messages))
    result = call_tool(
        model="claude-sonnet-5-5", system="s", user="u", tool_name="record_x",
        tool_description="d", input_schema=SCHEMA, settings=offline_settings(anthropic_api_key="test-key"),
    )
    assert result == {"x": "ok"}
    assert messages.calls[0]["tool_choice"] == {"type": "auto"}


def test_call_tool_fails_open_on_sdk_errors(monkeypatch):
    messages = FakeMessages(error=TimeoutError("slow"))
    monkeypatch.setattr(client_module, "_client", lambda *a: SimpleNamespace(messages=messages))
    result = call_tool(
        model="claude-haiku-5-5", system="s", user="u", tool_name="record_x",
        tool_description="d", input_schema=SCHEMA, settings=offline_settings(anthropic_api_key="test-key"),
    )
    assert result is None
