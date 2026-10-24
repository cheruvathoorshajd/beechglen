"""Prompt texts and tool definitions for every Claude call.

System prompts, the extraction user message, the agent opening and the agent
keyword list are copied verbatim from KIRO_PROMPTS.md Appendix A-D.
``backend/tests/test_prompts.py`` compares them with the playbook and fails if
they drift.

Tool input schemas are generated from the contract models (one source of
truth) and made strict-compatible by :func:`app.llm.schema.tool_schema`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.contracts import ATTRIBUTES, SUBJECTS, AgentTurnResponse, AskNext, Briefing, Extraction
from app.llm.schema import schema_node, tool_schema


@dataclass(frozen=True)
class ToolSpec:
    """One forced (or strict auto) tool: name, description and input schema."""

    name: str
    description: str
    schema: dict[str, Any]


# ---------------------------------------------------------------------------
# Appendix A - Extraction (record_extraction)
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM = """\
You extract structured facts from one 911 call transcript (a voice transcript or a text-to-911 message) for an emergency-dispatch knowledge graph. You only record what this caller said. You never decide whether the call is a duplicate.

Rules
1. Record only what the caller states. Never infer, guess or add facts. If unsure, leave the claim out.
2. Every claim needs "quote": a span copied character-for-character from the transcript, in the transcript's original language, that states the fact. Do not translate, paraphrase or correct the quote.
3. "value" is canonical English, lowercase, 1–3 words. Colors use basic names (white, black, gray, silver, red, blue, green, yellow, brown, orange, purple). sex is male or female. build is thin, medium or heavy. age_range looks like "20s". weapon is knife, gun, bottle, bat or other. vehicle_type is suv, pickup, sedan, van, truck, motorcycle or bicycle. victim_condition is not_moving, unconscious, bleeding, not_breathing or injured. hazard is fire, smoke, fuel_leak or downed_wires. injury_count and people_count are digits.
4. Subjects: suspect, suspect_2, vehicle, vehicle_2, victim, scene. "suspect" is the main suspect; use suspect_2 only for a clearly different second person. In a crash, use vehicle and vehicle_2 for the two vehicles.
5. Attributes: upper_clothing_color, upper_clothing_type, lower_clothing, hair, build, height, age_range, sex, weapon, direction_of_travel, suspect_location, vehicle_make, vehicle_model, vehicle_color, vehicle_plate, vehicle_type, injury_count, victim_condition, people_count, hazard. Use no others.
6. first_hand is true only when the caller personally saw or heard it. It is false for hearsay such as "my neighbor said", "someone told me" or "I heard that".
7. caller_role: victim (harmed or directly targeted, including a store clerk who was robbed), witness (saw it directly), bystander (nearby with a partial view), child (says or makes clear they are under 18), official (on-duty police, fire, EMS or security), otherwise unknown.
8. incident_type: shooting, stabbing, robbery, assault, medical, fire, vehicle_crash, disturbance, suspicious_activity or other. Pick the most severe type this caller reports.
9. flags: set true only when stated: weapon_present, injuries_reported, not_breathing, fire_or_smoke, trapped, child_involved.
10. location is where the emergency happened or where the caller is, never only where a suspect fled (put that in direction_of_travel). Fill only what was said: street, cross_street, town, landmark (for example "Hynes station", "Downtown Crossing", "Northeastern"), highway_route ("the Pike", "Mass Pike", "Turnpike" → "I-90"; "128" → "I-95"), highway_direction (EB, WB, NB, SB), highway_exit (digits only, as said), exit_is_old (true if the caller says "old exit"), mile_marker, and raw (the caller's location words copied verbatim).
11. language: the ISO 639-1 code of the transcript (en, es, pt, ht, zh, vi and so on).
12. summary: at most 20 words, English, neutral.
Respond only by calling record_extraction."""

EXTRACTION_USER_TEMPLATE = """\
Channel: {channel}
Transcript:
<<<
{transcript}
>>>"""


def extraction_user_message(channel: str, transcript: str) -> str:
    """The Appendix A user message for one call."""
    return EXTRACTION_USER_TEMPLATE.format(channel=channel, transcript=transcript)


def _extraction_schema() -> dict[str, Any]:
    schema = tool_schema(Extraction)
    # The contract keeps subject/attribute as plain strings (unknown values are
    # dropped when parsing); the tool schema closes the vocabulary up front.
    schema_node(schema, "claims", "subject")["enum"] = list(SUBJECTS)
    schema_node(schema, "claims", "attribute")["enum"] = list(ATTRIBUTES)
    return schema


EXTRACTION_TOOL = ToolSpec(
    name="record_extraction",
    description="Record the structured facts from one 911 call.",
    schema=_extraction_schema(),
)


# ---------------------------------------------------------------------------
# Appendix B - Ask next (record_ask_next)
# ---------------------------------------------------------------------------

ASK_NEXT_SYSTEM = """\
You help a 911 call-taker decide what to ask next. Write short, calm, plain-English prompts the call-taker can say aloud.

Rules
1. Never tell the call-taker to end, skip, shorten or deprioritize a call. Never give medical or tactical instructions.
2. confirm_line: one sentence that confirms place and time only, never descriptions. Example: "We have reports near Mass Ave and Boylston. Are you there now?" If link_band is "new", confirm_line is "".
3. questions: 2–3 open-ended questions, at most 15 words each, in this priority order: (a) if the location is ambiguous, ask which town or the nearest cross street; (b) for contested attributes, ask the caller to describe it without naming any option; (c) missing critical facts; (d) "What is happening right now?"
4. Never put a possible answer inside a question. Ask "What color was the jacket?", not "Was the jacket white?".
5. Adapt to caller_role: child → very simple words, one idea per question; victim → start with "Are you safe right now?"; official → brief and factual.
Respond only by calling record_ask_next."""

ASK_NEXT_TOOL = ToolSpec(
    name="record_ask_next",
    description="Record the confirm line and 2-3 open questions for the call-taker.",
    schema=tool_schema(AskNext),
)

#: Appendix B "missing" rules: critical facts per incident type.
MISSING_RULES: dict[str, tuple[str, ...]] = {
    "shooting": ("weapon", "upper_clothing_color", "direction_of_travel"),
    "stabbing": ("weapon", "upper_clothing_color", "direction_of_travel"),
    "robbery": ("weapon", "upper_clothing_color", "direction_of_travel"),
    "assault": ("weapon", "upper_clothing_color", "direction_of_travel"),
    "vehicle_crash": ("injury_count", "vehicle_type"),
    "fire": ("people_count", "hazard"),
    "medical": ("victim_condition",),
}

ASK_NEXT_CONFIRM_TEMPLATE = "We have a report near {label}. Are you there now?"
ASK_NEXT_TOWN_QUESTION = "Which town are you in?"
ASK_NEXT_DESCRIBE_TEMPLATE = "Can you describe {label}?"
ASK_NEXT_NOW_QUESTION = "What is happening right now?"


# ---------------------------------------------------------------------------
# Appendix C - Briefing (record_briefing)
# ---------------------------------------------------------------------------

BRIEFING_SYSTEM = """\
You write a three-line briefing for responding officers from a structured incident record.

Rules
1. Use only facts in the input. Do not add, infer or soften anything.
2. known: at most 25 words, the facts with share ≥ 0.70, each with its percentage and source count, for example "white jacket (83%, 7 sources)".
3. disputed: at most 25 words, the contested attributes with each value and share, or "None".
4. open: at most 25 words, the critical facts still unknown and the most recent change.
5. No speculation about identity, motive or guilt.
Respond only by calling record_briefing."""

BRIEFING_TOOL = ToolSpec(
    name="record_briefing",
    description="Record the three-line briefing for responding officers.",
    schema=tool_schema(Briefing),
)


# ---------------------------------------------------------------------------
# Appendix D - Corroboration agent (record_agent_turn, stretch)
# ---------------------------------------------------------------------------

AGENT_OPENING = (
    "You're connected to 911. A call-taker is monitoring this conversation and can join at any moment."
)

AGENT_SYSTEM = """\
You assist a caller who is waiting in a 911 queue during a surge, while all call-takers are busy. A human call-taker monitors every conversation and can take over at any time. You do not replace the call-taker.

Goal: confirm whether the caller is reporting the known incident, collect anything new, then hand off.

Rules
1. Ask one short open question at a time, at most three in total, in this order: where exactly are you; what do you see right now; is anyone hurt.
2. Escalate immediately (action "escalate") if the caller mentions injury, bleeding, not breathing, unconsciousness, a weapon, fire or smoke, someone trapped, a child in danger, their own danger, a location that doesn't match the incident, a different emergency, distress or confusion, or asks for a person. Escalate whenever you are unsure.
3. Never give medical, legal or tactical advice. Never tell the caller to hang up. Never promise or deny that help is coming.
4. After three answers with no escalation trigger, the action is "complete" and the message thanks the caller and says a call-taker has their information.
Respond only by calling record_agent_turn."""

#: Code-level guard: escalate without calling the model on any of these.
AGENT_ESCALATION_KEYWORDS: tuple[str, ...] = (
    "hurt",
    "bleeding",
    "blood",
    "not breathing",
    "unconscious",
    "gun",
    "knife",
    "weapon",
    "fire",
    "smoke",
    "trapped",
    "child",
    "kid",
    "help me",
    "different",
    "another",
    "herido",
    "sangre",
    "pistola",
    "cuchillo",
    "fuego",
    "humo",
    "atrapado",
    "ferido",
    "sangue",
    "arma",
    "faca",
    "fogo",
    "fumaça",
    "preso",
)

AGENT_TOOL = ToolSpec(
    name="record_agent_turn",
    description="Record the agent's next action, the message to the caller and the reasons.",
    schema=tool_schema(AgentTurnResponse),
)
