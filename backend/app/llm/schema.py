"""Tool schemas and fail-open parsing for Claude tool calls.

Two jobs, both driven by the Pydantic contracts so nothing is written twice:

``tool_schema``
    Turns a contract model into a JSON Schema that strict tool use accepts:
    ``$ref`` inlined, every object closed with ``additionalProperties: false``,
    every property required (nullable fields become ``["string", "null"]``),
    and keywords strict mode does not support (``minimum``, ``default`` ...)
    removed. Marking everything required keeps the schema under the API's
    limit of 24 optional parameters.

``sanitize``
    Turns a raw tool input into a contract instance without ever raising.
    Unknown keys are dropped, a field that fails validation falls back to its
    default, enum values are matched case-insensitively, and invalid list
    items (for example a malformed claim) are dropped one by one. A single bad
    value never invalidates the whole extraction (steering: fail-open).
"""

from __future__ import annotations

import copy
import types
from collections.abc import Mapping, Sequence
from typing import Any, TypeVar, Union, get_args, get_origin

from pydantic import BaseModel, TypeAdapter, ValidationError

M = TypeVar("M", bound=BaseModel)

#: JSON Schema keywords that strict tool use rejects or that add nothing for
#: the model. Constraints stay enforced by Pydantic when the input is parsed.
_UNSUPPORTED_KEYWORDS = frozenset(
    {
        "title",
        "default",
        "examples",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "multipleOf",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minProperties",
        "maxProperties",
    }
)


# ---------------------------------------------------------------------------
# Schema generation
# ---------------------------------------------------------------------------


def tool_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Strict-compatible JSON Schema for ``model``."""
    raw = model.model_json_schema()
    definitions = raw.pop("$defs", {})
    return _strictify(_inline(raw, definitions))


def schema_node(schema: dict[str, Any], *path: str) -> dict[str, Any]:
    """The sub-schema at ``path`` (property names), stepping through arrays.

    ``schema_node(s, "claims", "subject")`` returns the ``subject`` property of
    the claim objects inside the ``claims`` array.
    """
    node = schema
    for name in path:
        while node.get("type") == "array" or (
            isinstance(node.get("type"), list) and "array" in node["type"]
        ):
            node = node["items"]
        node = node["properties"][name]
    return node


def _inline(node: Any, definitions: dict[str, Any]) -> Any:
    """Replace every ``$ref`` (and single-ref ``allOf``) with its definition."""
    if isinstance(node, list):
        return [_inline(item, definitions) for item in node]
    if not isinstance(node, dict):
        return node

    if "allOf" in node and len(node["allOf"]) == 1 and "$ref" in node["allOf"][0]:
        merged = {key: value for key, value in node.items() if key != "allOf"}
        merged["$ref"] = node["allOf"][0]["$ref"]
        node = merged

    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        resolved = copy.deepcopy(definitions[name])
        for key, value in node.items():
            if key != "$ref":
                resolved.setdefault(key, value)
        return _inline(resolved, definitions)

    return {key: _inline(value, definitions) for key, value in node.items()}


def _strictify(node: Any) -> Any:
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node

    if "anyOf" in node:
        collapsed = _collapse_nullable(node)
        if collapsed is not None:
            return collapsed

    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in _UNSUPPORTED_KEYWORDS:
            continue
        if key == "properties":
            out[key] = {name: _strictify(sub) for name, sub in value.items()}
        elif key in ("items", "anyOf"):
            out[key] = _strictify(value)
        else:
            out[key] = value

    if out.get("type") == "object" or "properties" in out:
        out["type"] = "object"
        out.setdefault("properties", {})
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def _collapse_nullable(node: dict[str, Any]) -> dict[str, Any] | None:
    """``anyOf: [{type: X}, {type: null}]`` -> ``{type: [X, "null"]}``.

    Only scalar options collapse; anything else stays an ``anyOf``.
    """
    options = node["anyOf"]
    non_null = [option for option in options if option.get("type") != "null"]
    if len(non_null) != 1 or len(non_null) == len(options):
        return None
    base = _strictify(non_null[0])
    kind = base.get("type")
    if not isinstance(kind, str) or kind in ("object", "array"):
        return None
    merged = dict(base)
    merged["type"] = [kind, "null"]
    if "enum" in merged:
        merged["enum"] = [*merged["enum"], None]
    if "description" in node and "description" not in merged:
        merged["description"] = node["description"]
    return merged


# ---------------------------------------------------------------------------
# Fail-open parsing
# ---------------------------------------------------------------------------

_DROP = object()
_ADAPTERS: dict[tuple[type[BaseModel], str], TypeAdapter[Any]] = {}


def sanitize(model: type[M], raw: Any) -> M | None:
    """Best-effort ``model`` instance from ``raw``; None only if nothing fits."""
    if isinstance(raw, model):
        return raw
    if not isinstance(raw, Mapping):
        return None

    clean: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if name in raw:
            key = name
        elif field.alias and field.alias in raw:
            key = field.alias
        else:
            continue
        value = _clean_value(model, name, raw[key])
        if value is not _DROP:
            clean[name] = value

    try:
        return model.model_validate(clean)
    except ValidationError:
        return None


def _clean_value(model: type[BaseModel], name: str, value: Any) -> Any:
    annotation = model.model_fields[name].annotation

    nested = _model_type(annotation)
    if nested is not None:
        if value is None and _allows_none(annotation):
            return None
        parsed = sanitize(nested, value)
        return parsed if parsed is not None else _DROP

    item_model = _list_item_model(annotation)
    if item_model is not None:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
            return _DROP
        items = (sanitize(item_model, item) for item in value)
        return [item for item in items if item is not None]

    adapter = _adapter(model, name)
    for candidate in _candidates(value):
        try:
            return adapter.validate_python(candidate)
        except ValidationError:
            continue
    return _DROP


def _candidates(value: Any) -> list[Any]:
    """The value as given, then a trimmed lowercase variant for enum casing."""
    if isinstance(value, str):
        folded = value.strip().lower()
        return [value, folded] if folded != value else [value]
    return [value]


def _adapter(model: type[BaseModel], name: str) -> TypeAdapter[Any]:
    key = (model, name)
    if key not in _ADAPTERS:
        _ADAPTERS[key] = TypeAdapter(model.model_fields[name].rebuild_annotation())
    return _ADAPTERS[key]


def _union_args(annotation: Any) -> tuple[Any, ...] | None:
    if get_origin(annotation) in (Union, types.UnionType):
        return get_args(annotation)
    return None


def _allows_none(annotation: Any) -> bool:
    args = _union_args(annotation)
    return args is not None and type(None) in args


def _model_type(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    args = _union_args(annotation)
    if args is not None:
        non_null = [arg for arg in args if arg is not type(None)]
        if len(non_null) == 1:
            return _model_type(non_null[0])
    return None


def _list_item_model(annotation: Any) -> type[BaseModel] | None:
    if get_origin(annotation) in (list, tuple, Sequence):
        args = get_args(annotation)
        if args:
            return _model_type(args[0])
    return None
