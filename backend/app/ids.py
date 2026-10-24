"""Identifier generation.

Sequential, prefixed identifiers keep logs, audit entries and test assertions
readable. The counters are process-local and reset with the graph, which is
exactly the lifetime of the in-memory store.
"""

from __future__ import annotations

import threading
from collections import defaultdict

_PREFIXES = {
    "call": "c",
    "incident": "inc",
    "claim": "clm",
    "lead": "lead",
    "audit": "aud",
}

_lock = threading.Lock()
_counters: defaultdict[str, int] = defaultdict(int)


def next_id(kind: str) -> str:
    """Return the next identifier for ``kind``, e.g. ``inc-0003``."""
    prefix = _PREFIXES.get(kind, kind)
    with _lock:
        _counters[kind] += 1
        number = _counters[kind]
    return f"{prefix}-{number:04d}"


def reset_ids() -> None:
    """Restart every counter. Called when the graph is reset."""
    with _lock:
        _counters.clear()
