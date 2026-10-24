"""Anthropic client wrapper.

One narrow entry point, call_tool, which forces Claude to answer through a
single named tool and returns the input dictionary of that tool.

Three rules hold everywhere (steering: tech.md):

* Structured output only. We never parse free text. The model must answer by
  calling the one tool we offer, so the response shape is the tool schema.
* temperature 0. The demo has to be reproducible.
* Fail-open. Timeouts, refusals, malformed tool calls and missing API keys all
  return None. Callers supply a deterministic fallback; no LLM failure ever
  propagates to an API caller or blocks a call from entering the graph.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Generous enough for a full extraction, small enough to stay fast.
DEFAULT_MAX_TOKENS = 2048


class ToolCaller(Protocol):
    """Callable shape of call_tool.

    Declared so extract, ask-next and briefing can accept a fake in tests
    without importing the Anthropic SDK.
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
    """Ask Claude to answer by calling tool_name; return the tool input.

    Args:
        model: Model id, from CLAUDE_MODEL_EXTRACT or CLAUDE_MODEL_FAST.
        system: System prompt, verbatim from KIRO_PROMPTS.md Appendix A-D.
        user: User message.
        tool_name: The single tool the model is forced to call.
        tool_description: Short description shown to the model.
        input_schema: JSON Schema for the tool input.
        max_tokens: Response cap.
        settings: Process settings; defaults to the cached process settings.

    Returns:
        The tool input as a dict, or None if the call failed for any reason.
    """
