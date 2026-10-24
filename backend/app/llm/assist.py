"""Ask-next prompts and officer briefings (KIRO_PROMPTS.md Appendix B and C).

Both use CLAUDE_MODEL_FAST through one tool and fall back to deterministic
templates on any failure, so they never block the operator. Results are cached
in memory per call or incident and recomputed when the incident changes (its
``last_seen`` or timeline moves).

Safety rules enforced in code, not just in the prompt:

* Ask-next questions must not name any value of a contested attribute, so the
  call-taker never suggests an answer ("Was the jacket white?").
* 2-3 questions; a ``new`` link band never gets a confirm line.
"""

from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable, Sequence
from typing import Any

from app.config import Settings, get_settings
from app.contracts import AskNext, AttributeConsensus, Briefing, CallDetail, IncidentDetail, attribute_label
from app.llm.client import ToolCaller, call_tool
from app.llm.prompts import (
    ASK_NEXT_CONFIRM_TEMPLATE,
    ASK_NEXT_DESCRIBE_TEMPLATE,
    ASK_NEXT_NOW_QUESTION,
    ASK_NEXT_SYSTEM,
    ASK_NEXT_TOOL,
    ASK_NEXT_TOWN_QUESTION,
    BRIEFING_SYSTEM,
    BRIEFING_TOOL,
    MISSING_RULES,
    ToolSpec,
)
from app.llm.schema import sanitize

KNOWN_MIN_SHARE = 0.70
MIN_QUESTIONS = 2
MAX_QUESTIONS = 3
BRIEFING_MAX_WORDS = 25
VICTIM_SAFETY_QUESTION = "Are you safe right now?"
UNKNOWN_LABEL = "Unknown location"

#: Nouns that read naturally after a value in the briefing ("white jacket").
_PAIRED_NOUNS = {"upper_clothing_color": "upper_clothing_type", "vehicle_color": "vehicle_type"}


# ---------------------------------------------------------------------------
# Inputs (Appendix B and C user messages)
# ---------------------------------------------------------------------------


def missing_facts(incident_type: str, consensus: Sequence[AttributeConsensus]) -> list[str]:
    """Appendix B rules: a critical fact is missing when consensus has no value."""
    present = {entry.attribute for entry in consensus if entry.values}
    return [attribute for attribute in MISSING_RULES.get(incident_type, ()) if attribute not in present]


def ask_next_input(call: CallDetail, incident: IncidentDetail) -> dict[str, Any]:
    consensus = incident.consensus
    return {
        "caller_role": call.extraction.caller_role,
        "call_summary": call.extraction.summary,
        "link_band": call.link.band,
        "known_facts": [
            {"attribute": c.attribute, "top_value": c.values[0].value, "share": c.values[0].share}
            for c in consensus
            if c.values and not c.contested and c.values[0].share >= KNOWN_MIN_SHARE
        ],
        "contested": [
            {"attribute": c.attribute, "values": [v.value for v in c.values]} for c in consensus if c.contested
        ],
        "missing": missing_facts(incident.incident.type, consensus),
        "location": {
            "label": call.location.label,
            "confidence": call.location.confidence,
            "ambiguous": call.location.ambiguous,
            "candidates": list(call.location.candidates),
        },
    }


def briefing_input(incident: IncidentDetail) -> dict[str, Any]:
    return {
        "consensus": [entry.model_dump(mode="json") for entry in incident.consensus],
        "contradictions": [entry.model_dump(mode="json") for entry in incident.contradictions],
        "dispatch": incident.dispatch.model_dump(mode="json"),
        "timeline": [
            {"t": entry.t.isoformat(), "event": entry.event, "call_id": entry.call_id}
            for entry in incident.timeline[-5:]
        ],
    }


# ---------------------------------------------------------------------------
# Template fallbacks
# ---------------------------------------------------------------------------


def _describe(attribute: str) -> str:
    return ASK_NEXT_DESCRIBE_TEMPLATE.format(label=attribute_label(attribute))


def template_ask_next(payload: dict[str, Any]) -> AskNext:
    """Appendix B fallback, plus the victim-safety question first for victims."""
    label = payload["location"]["label"]
    confirm = ""
    if payload["link_band"] != "new" and label and label != UNKNOWN_LABEL:
        confirm = ASK_NEXT_CONFIRM_TEMPLATE.format(label=label)

    questions: list[str] = []
    if payload["caller_role"] == "victim":
        questions.append(VICTIM_SAFETY_QUESTION)
    if payload["location"]["ambiguous"]:
        questions.append(ASK_NEXT_TOWN_QUESTION)
    if payload["contested"]:
        questions.append(_describe(payload["contested"][0]["attribute"]))
    if len(questions) < MIN_QUESTIONS and payload["missing"]:
        questions.append(_describe(payload["missing"][0]))
    questions.append(ASK_NEXT_NOW_QUESTION)
    return AskNext(confirm_line=confirm, questions=list(dict.fromkeys(questions))[:MAX_QUESTIONS])


def _plural(count: int) -> str:
    return f"{count} source" if count == 1 else f"{count} sources"


def _words(attribute: str) -> str:
    return attribute.replace("_", " ")


def _within(parts: Sequence[str], limit: int, separator: str) -> str:
    """Join whole parts while the result stays within ``limit`` words."""
    kept: list[str] = []
    for part in parts:
        candidate = separator.join([*kept, part])
        if len(candidate.split()) > limit:
            break
        kept.append(part)
    return separator.join(kept)


def template_briefing(incident: IncidentDetail) -> Briefing:
    """Appendix C fallback: the three lines straight from the consensus."""
    consensus = incident.consensus
    index = {(c.subject, c.attribute): c for c in consensus}

    known_parts: list[str] = []
    used: set[tuple[str, str]] = set()
    ranked = sorted(
        (c for c in consensus if c.values and not c.contested and c.values[0].share >= KNOWN_MIN_SHARE),
        key=lambda c: (-c.values[0].sources, -c.values[0].share, c.subject, c.attribute),
    )
    for entry in ranked:
        key = (entry.subject, entry.attribute)
        if key in used:
            continue
        top = entry.values[0]
        noun_key = (entry.subject, _PAIRED_NOUNS.get(entry.attribute, ""))
        noun = index.get(noun_key)
        if noun is not None and noun.values and not noun.contested:
            phrase = f"{top.value} {noun.values[0].value}"
            used.add(noun_key)
        else:
            phrase = f"{_words(entry.attribute)} {top.value}"
        used.add(key)
        known_parts.append(f"{phrase} ({round(top.share * 100)}%, {_plural(top.sources)})")
    known = _within(known_parts, BRIEFING_MAX_WORDS, "; ") or "No fact has 70% agreement yet."

    disputed_parts = [
        f"{_words(c.attribute)}: " + ", ".join(f"{v.value} {round(v.share * 100)}%" for v in c.values)
        for c in consensus
        if c.contested
    ]
    disputed = _within(disputed_parts, BRIEFING_MAX_WORDS, "; ") or "None"

    open_parts: list[str] = []
    missing = missing_facts(incident.incident.type, consensus)
    if missing:
        open_parts.append("Unknown: " + ", ".join(_words(a) for a in missing) + ".")
    if incident.timeline:
        open_parts.append(f"Latest: {incident.timeline[-1].event}.")
    open_line = _within(open_parts, BRIEFING_MAX_WORDS, " ") or "None"
    return Briefing(known=known, disputed=disputed, open=open_line)


# ---------------------------------------------------------------------------
# Validation of model output
# ---------------------------------------------------------------------------


def _names_any(text: str, values: set[str]) -> bool:
    folded = text.casefold()
    return any(re.search(rf"\b{re.escape(value.casefold())}\b", folded) for value in values if value)


def validated_ask_next(raw: Any, payload: dict[str, Any]) -> AskNext | None:
    parsed = sanitize(AskNext, raw)
    if parsed is None:
        return None
    contested_values = {value for item in payload["contested"] for value in item["values"]}
    questions = [
        question.strip()
        for question in parsed.questions
        if question.strip() and not _names_any(question, contested_values)
    ]
    if len(questions) < MIN_QUESTIONS:
        return None
    confirm = "" if payload["link_band"] == "new" else parsed.confirm_line.strip()
    return AskNext(confirm_line=confirm, questions=questions[:MAX_QUESTIONS])


def validated_briefing(raw: Any) -> Briefing | None:
    parsed = sanitize(Briefing, raw)
    if parsed is None or not all(part.strip() for part in (parsed.known, parsed.disputed, parsed.open)):
        return None
    return Briefing(known=parsed.known.strip(), disputed=parsed.disputed.strip(), open=parsed.open.strip())


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AssistService:
    def __init__(
        self,
        *,
        tool_caller: ToolCaller | None = None,
        settings: Callable[[], Settings] = get_settings,
    ) -> None:
        self._tool_caller = tool_caller
        self._settings = settings
        self._lock = threading.Lock()
        self._ask: dict[tuple[Any, ...], AskNext] = {}
        self._brief: dict[tuple[Any, ...], Briefing] = {}

    def clear(self) -> None:
        with self._lock:
            self._ask.clear()
            self._brief.clear()

    def ask_next(self, call: CallDetail, incident: IncidentDetail) -> AskNext:
        key = (
            call.link.call_id,
            incident.incident.id,
            call.link.band,
            incident.incident.last_seen.isoformat(),
            len(incident.timeline),
        )
        with self._lock:
            if key in self._ask:
                return self._ask[key]
        payload = ask_next_input(call, incident)
        raw = self._call(ASK_NEXT_SYSTEM, ASK_NEXT_TOOL, payload)
        result = (validated_ask_next(raw, payload) if raw is not None else None) or template_ask_next(payload)
        with self._lock:
            self._ask[key] = result
        return result

    def briefing(self, incident: IncidentDetail) -> Briefing:
        key = (incident.incident.id, incident.incident.last_seen.isoformat(), len(incident.timeline))
        with self._lock:
            if key in self._brief:
                return self._brief[key]
        raw = self._call(BRIEFING_SYSTEM, BRIEFING_TOOL, briefing_input(incident))
        result = (validated_briefing(raw) if raw is not None else None) or template_briefing(incident)
        with self._lock:
            self._brief[key] = result
        return result

    def _call(self, system: str, tool: ToolSpec, payload: dict[str, Any]) -> dict[str, Any] | None:
        settings = self._settings()
        if not settings.llm_enabled:
            return None
        request = {
            "model": settings.claude_model_fast,
            "system": system,
            "user": json.dumps(payload, ensure_ascii=False),
            "tool_name": tool.name,
            "tool_description": tool.description,
            "input_schema": tool.schema,
            "max_tokens": 1024,
        }
        if self._tool_caller is None:
            return call_tool(**request, settings=settings)
        return self._tool_caller(**request)
