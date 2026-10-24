"""Strict tool schemas and fail-open parsing of tool output."""

from __future__ import annotations

from typing import Any

from app.contracts import AskNext, Extraction
from app.llm.schema import sanitize, schema_node, tool_schema

UNSUPPORTED = {"$ref", "$defs", "allOf", "title", "default", "minimum", "maximum"}


def walk(node: Any):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def test_extraction_schema_is_strict_compatible():
    schema = tool_schema(Extraction)
    objects = [n for n in walk(schema) if n.get("type") == "object"]
    assert objects, "expected nested objects"
    for node in objects:
        assert node["additionalProperties"] is False
        assert sorted(node["required"]) == sorted(node["properties"])
    for node in walk(schema):
        assert not UNSUPPORTED & set(node), node
    unions = [n for n in walk(schema) if isinstance(n.get("type"), list) or "anyOf" in n]
    assert len(unions) <= 16


def test_nullable_fields_become_type_arrays():
    schema = tool_schema(Extraction)
    assert schema_node(schema, "location", "street")["type"] == ["string", "null"]
    assert schema_node(schema, "location", "mile_marker")["type"] == ["number", "null"]
    assert schema_node(schema, "claims", "subject")["type"] == "string"
    assert "enum" in schema_node(schema, "incident_type")


def test_sanitize_drops_unknown_keys_at_every_level():
    raw = {
        "language": "es",
        "incident_type": "robbery",
        "caller_role": "witness",
        "confidence_overall": 0.9,
        "flags": {"weapon_present": True, "panic": True},
        "location": {"street": "Mass Ave", "cross_street": "Boylston", "zip": "02115"},
        "claims": [
            {
                "subject": "suspect",
                "attribute": "upper_clothing_color",
                "value": "white",
                "quote": "chaqueta blanca",
                "first_hand": True,
                "confidence": 0.9,
                "notes": "extra",
            }
        ],
        "summary": "Robbery at Mass Ave and Boylston.",
    }
    extraction = sanitize(Extraction, raw)
    assert extraction is not None
    assert extraction.language == "es"
    assert extraction.flags.weapon_present is True
    assert extraction.location.cross_street == "Boylston"
    assert extraction.claims[0].quote == "chaqueta blanca"


def test_sanitize_resets_invalid_values_and_fixes_enum_casing():
    raw = {"incident_type": "burglary", "caller_role": "Witness", "flags": "not a dict", "summary": 42}
    extraction = sanitize(Extraction, raw)
    assert extraction is not None
    assert extraction.incident_type == "other"
    assert extraction.caller_role == "witness"
    assert extraction.flags.any_set() is False


def test_sanitize_drops_bad_claims_one_by_one():
    raw = {
        "claims": [
            {"subject": "suspect", "attribute": "weapon", "value": "knife", "quote": "pulled a knife", "first_hand": True, "confidence": 1},
            {"subject": "suspect", "attribute": "weapon", "value": "knife"},
            {"subject": "suspect", "attribute": "shoe_size", "value": "10", "quote": "size 10", "first_hand": True, "confidence": 1},
            "not a claim",
            {"subject": "suspect", "attribute": "build", "value": "thin", "quote": "thin", "first_hand": True, "confidence": 7},
        ]
    }
    extraction = sanitize(Extraction, raw)
    assert extraction is not None
    assert [(c.attribute, c.value) for c in extraction.claims] == [("weapon", "knife"), ("build", "thin")]
    assert extraction.claims[1].confidence == 1.0


def test_sanitize_rejects_non_objects():
    assert sanitize(Extraction, None) is None
    assert sanitize(Extraction, ["a"]) is None
    assert sanitize(AskNext, {"confirm_line": "Hi", "questions": ["What happened?"], "x": 1}).questions == ["What happened?"]
