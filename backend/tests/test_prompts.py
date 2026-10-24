"""Prompt texts must match KIRO_PROMPTS.md Appendix A-D verbatim."""

from __future__ import annotations

import re

import pytest

from app.contracts import ATTRIBUTES, SUBJECTS
from app.llm import prompts
from app.llm.schema import schema_node
from app.paths import REPO_ROOT

PLAYBOOK = (REPO_ROOT / "KIRO_PROMPTS.md").read_text(encoding="utf-8")


def appendix(letter: str) -> str:
    match = re.search(rf"^## Appendix {letter}\b.*?(?=^## Appendix |\Z)", PLAYBOOK, re.S | re.M)
    assert match, f"Appendix {letter} not found"
    return match.group(0)


def blocks(letter: str) -> list[str]:
    return re.findall(r"```[a-z]*\n(.*?)\n```", appendix(letter), re.S)


@pytest.mark.parametrize(
    ("letter", "index", "constant"),
    [
        ("A", 0, "EXTRACTION_SYSTEM"),
        ("A", 1, "EXTRACTION_USER_TEMPLATE"),
        ("B", 0, "ASK_NEXT_SYSTEM"),
        ("C", 0, "BRIEFING_SYSTEM"),
        ("D", 0, "AGENT_OPENING"),
        ("D", 1, "AGENT_SYSTEM"),
    ],
)
def test_prompt_matches_playbook_verbatim(letter, index, constant):
    assert getattr(prompts, constant) == blocks(letter)[index]


def test_agent_keyword_guard_matches_playbook():
    sentence = re.search(r"case-insensitive: (.*?)\. Any model error", appendix("D"), re.S).group(1)
    expected = tuple(word.strip() for word in sentence.split(","))
    assert prompts.AGENT_ESCALATION_KEYWORDS == expected


def test_ask_next_fallback_strings_come_from_appendix_b():
    text = appendix("B")
    assert prompts.ASK_NEXT_TOWN_QUESTION in text
    assert prompts.ASK_NEXT_NOW_QUESTION in text
    assert prompts.ASK_NEXT_CONFIRM_TEMPLATE.replace("{label}", "{location label}") in text
    assert prompts.ASK_NEXT_DESCRIBE_TEMPLATE.replace("{label}", "{plain label}") in text


def test_tool_names_and_extraction_vocabulary():
    assert prompts.EXTRACTION_TOOL.name == "record_extraction"
    assert prompts.EXTRACTION_TOOL.description == "Record the structured facts from one 911 call."
    assert (prompts.ASK_NEXT_TOOL.name, prompts.BRIEFING_TOOL.name, prompts.AGENT_TOOL.name) == (
        "record_ask_next", "record_briefing", "record_agent_turn",
    )
    schema = prompts.EXTRACTION_TOOL.schema
    assert schema_node(schema, "claims", "subject")["enum"] == list(SUBJECTS)
    assert schema_node(schema, "claims", "attribute")["enum"] == list(ATTRIBUTES)


def test_user_message_fills_channel_and_transcript():
    message = prompts.extraction_user_message("text", "crash pike eb {braces} ok")
    assert message == "Channel: text\nTranscript:\n<<<\ncrash pike eb {braces} ok\n>>>"
