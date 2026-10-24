"""Claim extraction with Claude (README -> "1. Extract").

Claude reads one transcript and answers through the ``record_extraction``
tool, whose input schema is the ``Extraction`` contract. The raw tool input is
sanitized (unknown keys dropped, invalid values reset, bad claims dropped)
before validation, so one malformed field never loses the whole call.

Cache-first: results are stored at
``data/cache/extractions/<sha256(transcript)>.json``.

* ``DEMO_MODE=cache_first``: cache, then the API on a miss.
* ``DEMO_MODE=offline``: cache only; a miss returns the minimal extraction.

Any failure (no key, timeout, refusal, invalid output) returns the minimal
extraction: type ``other``, no claims, summary = first 20 words. The call still
enters the graph. A scenario's ``caller_role_hint`` overrides the extracted
caller role.

Cache files wrap the extraction with its transcript so a wrong entry can be
found and corrected by hand (KIRO_PROMPTS.md step I2).
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from app.config import Settings, get_settings
from app.contracts import CallIn, Extraction
from app.llm.client import ToolCaller, call_tool
from app.llm.prompts import EXTRACTION_SYSTEM, EXTRACTION_TOOL, extraction_user_message
from app.llm.schema import sanitize
from app.paths import EXTRACTION_CACHE_DIR
from app.text import first_words, sha256_of

logger = logging.getLogger(__name__)

SUMMARY_WORDS = 20

PrecomputeOutcome = Literal["cached", "extracted", "failed"]


def cache_path(transcript: str, cache_dir: Path = EXTRACTION_CACHE_DIR) -> Path:
    """Cache file for a transcript: ``<sha256(transcript)>.json``."""
    return cache_dir / f"{sha256_of(transcript)}.json"


def minimal_extraction(call: CallIn) -> Extraction:
    """Fail-open fallback: type ``other``, no claims, first 20 words as summary."""
    return Extraction(summary=first_words(call.transcript, SUMMARY_WORDS))


def normalize_extraction(extraction: Extraction) -> Extraction:
    """Canonical values (lowercase, single spaces); drop empty and duplicate claims.

    Claims with an empty quote are kept on purpose: the quote guard rejects
    them, and guard stats should count them.
    """
    seen: set[tuple[str, str, str, str]] = set()
    claims = []
    for claim in extraction.claims:
        value = " ".join(claim.value.lower().split())
        quote = claim.quote.strip()
        key = (claim.subject, claim.attribute, value, quote)
        if not value or key in seen:
            continue
        seen.add(key)
        claims.append(claim.model_copy(update={"value": value, "quote": quote}))
    return extraction.model_copy(update={"claims": claims, "summary": extraction.summary.strip()})


def apply_role_hint(extraction: Extraction, call: CallIn) -> Extraction:
    """A scenario's ``caller_role_hint`` overrides the extracted caller role."""
    if call.caller_role_hint is None:
        return extraction
    return extraction.model_copy(update={"caller_role": call.caller_role_hint})


def load_cached(path: Path) -> Extraction | None:
    """The cached extraction at ``path``, or None if missing or unreadable."""
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("Ignoring unreadable extraction cache %s: %s", path.name, exc)
        return None
    raw = payload.get("extraction", payload) if isinstance(payload, dict) else None
    extraction = sanitize(Extraction, raw)
    if extraction is None:
        logger.warning("Ignoring invalid extraction cache %s", path.name)
    return extraction


def save_cached(path: Path, call: CallIn, extraction: Extraction, model: str) -> None:
    """Write the cache file atomically (temp file, then rename)."""
    payload = {
        "transcript": call.transcript,
        "channel": call.channel,
        "model": model,
        "extraction": extraction.model_dump(mode="json"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


class Extractor:
    """Cache-first extractor. Callable as ``extractor(call) -> Extraction``.

    Dependencies are injectable so tests run without the SDK or the network.
    """

    def __init__(
        self,
        *,
        tool_caller: ToolCaller | None = None,
        settings: Callable[[], Settings] = get_settings,
        cache_dir: Path = EXTRACTION_CACHE_DIR,
    ) -> None:
        self._tool_caller = tool_caller
        self._settings = settings
        self._cache_dir = cache_dir

    def __call__(self, call: CallIn) -> Extraction:
        return apply_role_hint(self.extract_raw(call), call)

    def extract_raw(self, call: CallIn) -> Extraction:
        """Extraction before the role-hint override."""
        settings = self._settings()
        path = cache_path(call.transcript, self._cache_dir)
        cached = load_cached(path)
        if cached is not None:
            return cached
        if settings.demo_mode == "offline" or not settings.llm_enabled:
            return minimal_extraction(call)
        live = self._call_model(call, settings)
        if live is None:
            return minimal_extraction(call)
        save_cached(path, call, live, settings.claude_model_extract)
        return live

    def precompute(self, call: CallIn) -> PrecomputeOutcome:
        """Fill the cache for one call; used by scripts/precompute_extractions.py."""
        settings = self._settings()
        path = cache_path(call.transcript, self._cache_dir)
        if load_cached(path) is not None:
            return "cached"
        if not settings.llm_enabled:
            return "failed"
        live = self._call_model(call, settings)
        if live is None:
            return "failed"
        save_cached(path, call, live, settings.claude_model_extract)
        return "extracted"

    def _call_model(self, call: CallIn, settings: Settings) -> Extraction | None:
        request = {
            "model": settings.claude_model_extract,
            "system": EXTRACTION_SYSTEM,
            "user": extraction_user_message(call.channel, call.transcript),
            "tool_name": EXTRACTION_TOOL.name,
            "tool_description": EXTRACTION_TOOL.description,
            "input_schema": EXTRACTION_TOOL.schema,
        }
        if self._tool_caller is None:
            raw = call_tool(**request, settings=settings)
        else:
            raw = self._tool_caller(**request)
        if raw is None:
            return None
        parsed = sanitize(Extraction, raw)
        return normalize_extraction(parsed) if parsed is not None else None


_default_extractor = Extractor()


def extract(call: CallIn) -> Extraction:
    """Lane B interface (structure.md): extraction for one call, never raises."""
    return _default_extractor(call)
