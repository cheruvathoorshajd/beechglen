"""Anthropic client wrapper.

One narrow entry point, :func:`call_tool`, which makes Claude answer through a
single named tool and returns the input dictionary of that tool.

Rules that hold everywhere (steering: tech.md):

* Structured output only. The model answers by calling the one tool we offer,
  so the response shape is the tool schema. Free text is never parsed.
* Deterministic where the model allows it. ``temperature`` 0 and a forced
  ``tool_choice`` are sent only to models that accept them; Claude 5.x models
  reject sampling parameters and Claude Sonnet 5.5 rejects forced tool choice
  (it gets ``tool_choice: auto`` plus ``strict: true`` instead). Demo
  determinism comes from the extraction cache, not from sampling.
* Fail-open. Timeouts, refusals, malformed tool calls and missing API keys all
  return None. Callers supply a deterministic fallback; no LLM failure ever
  propagates to an API caller or blocks a call from entering the graph.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

#: Room for a full extraction on the newer tokenizer, which counts about 30%
#: more tokens than Claude 4.5-era models for the same text.
DEFAULT_MAX_TOKENS = 4096


class ToolCaller(Protocol):
    """Callable shape of :func:`call_tool`.

    Declared so extract, ask-next, briefing and the agent can accept a fake in
    tests without importing the Anthropic SDK.
    """

    def __call__(
        self,
        *,
        model: str,
        system: str,
        user: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict[str, Any],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any] | None: ...


# ---------------------------------------------------------------------------
# Per-model request settings
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ModelProfile:
    """Which request settings a model accepts."""

    accepts_temperature: bool
    accepts_forced_tool: bool
    thinking: Mapping[str, Any] | None = None


_MODEL_ID = re.compile(r"claude-(opus|sonnet|haiku|fable|mythos)-(\d+)(?:-(\d{1,2}))?(?!\d)")

#: Turns off up-front thinking on Claude Sonnet 5.5 (its "disabled" value
#: returns a 400). Keeps extraction fast enough for the 20-second timeout.
_BETWEEN_TOOLS = {"type": "between_tools"}


def model_profile(model: str) -> ModelProfile:
    """Request settings for ``model``, from its family and version.

    Unknown naming gets the conservative modern profile: no sampling
    parameters and no forced tool choice.
    """
    match = _MODEL_ID.search(model)
    if match is None:
        return ModelProfile(accepts_temperature=False, accepts_forced_tool=False)

    family = match.group(1)
    version = (int(match.group(2)), int(match.group(3) or 0))

    accepts_temperature = version <= (4, 6)
    rejects_forced = (family in ("opus", "sonnet") and version >= (5, 5)) or (
        family in ("fable", "mythos") and version >= (5, 1)
    )
    thinking = _BETWEEN_TOOLS if family == "sonnet" and version >= (5, 5) else None
    return ModelProfile(
        accepts_temperature=accepts_temperature,
        accepts_forced_tool=not rejects_forced,
        thinking=thinking,
    )


def build_request(
    *,
    model: str,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    """Keyword arguments for ``messages.create`` that offer exactly one tool."""
    profile = model_profile(model)
    tool: dict[str, Any] = {
        "name": tool_name,
        "description": tool_description,
        "input_schema": input_schema,
        "strict": True,
    }
    request: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "tools": [tool],
        "tool_choice": (
            {"type": "tool", "name": tool_name}
            if profile.accepts_forced_tool
            else {"type": "auto"}
        ),
    }
    if profile.accepts_temperature:
        request["temperature"] = 0
    if profile.thinking is not None:
        request["thinking"] = dict(profile.thinking)
    return request


def parse_tool_input(response: Any, tool_name: str) -> dict[str, Any] | None:
    """The input of the first ``tool_name`` call in ``response``, else None.

    Content blocks are selected by type, never by position, because newer
    models can return thinking blocks before the tool call.
    """
    if getattr(response, "stop_reason", None) in ("refusal", "max_tokens"):
        return None
    for block in getattr(response, "content", None) or ():
        if getattr(block, "type", None) != "tool_use" or getattr(block, "name", None) != tool_name:
            continue
        data = getattr(block, "input", None)
        return dict(data) if isinstance(data, Mapping) else None
    return None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@lru_cache(maxsize=4)
def _client(api_key: str, timeout_s: float, max_retries: int) -> Any:
    import anthropic

    return anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=max_retries)


def call_tool(
    *,
    model: str,
    system: str,
    user: str,
    tool_name: str,
    tool_description: str,
    input_schema: dict[str, Any],
    max_tokens: int = DEFAULT_MAX_TOKENS,
    settings: Settings | None = None,
) -> dict[str, Any] | None:
    """Ask Claude to answer by calling ``tool_name``; return the tool input.

    Args:
        model: Model id, from CLAUDE_MODEL_EXTRACT or CLAUDE_MODEL_FAST.
        system: System prompt, verbatim from KIRO_PROMPTS.md Appendix A-D.
        user: User message.
        tool_name: The single tool the model must answer with.
        tool_description: Short description shown to the model.
        input_schema: Strict-compatible JSON Schema for the tool input.
        max_tokens: Response cap.
        settings: Process settings; defaults to the cached process settings.

    Returns:
        The tool input as a dict, or None if the call failed for any reason.
        The caller validates the dict; this function never raises.
    """
    active = settings or get_settings()
    if not active.llm_enabled or active.anthropic_api_key is None:
        return None

    request = build_request(
        model=model,
        system=system,
        user=user,
        tool_name=tool_name,
        tool_description=tool_description,
        input_schema=input_schema,
        max_tokens=max_tokens,
    )
    try:
        client = _client(active.anthropic_api_key, active.llm_timeout_s, active.llm_max_retries)
        response = client.messages.create(**request)
    except Exception as exc:  # noqa: BLE001 - fail-open by design
        logger.warning("LLM call %s on %s failed: %s: %s", tool_name, model, type(exc).__name__, str(exc)[:300])
        return None

    result = parse_tool_input(response, tool_name)
    if result is None:
        logger.warning(
            "LLM call %s on %s returned no tool input (stop_reason=%s)",
            tool_name,
            model,
            getattr(response, "stop_reason", None),
        )
    return result
