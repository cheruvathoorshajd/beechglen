"""Identifier generation.

Sequential, prefixed identifiers keep logs, audit entries and test assertions
readable. Each GraphStore and AuditLog owns its own :class:`IdGenerator`, so
counters reset with the store they belong to and two stores in one process
(tests, the evaluation script) never hand out colliding ids.
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


class IdGenerator:
    """Thread-safe per-kind counters: ``inc-0001``, ``inc-0002``..."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: defaultdict[str, int] = defaultdict(int)

    def next(self, kind: str) -> str:
        prefix = _PREFIXES.get(kind, kind)
        with self._lock:
            self._counters[kind] += 1
            number = self._counters[kind]
        return f"{prefix}-{number:04d}"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
