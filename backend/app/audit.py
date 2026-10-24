"""Append-only audit log.

Every automated link decision and every human override is recorded here. The
log is write-once: entries are never edited or removed, only appended and read.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from app.contracts import Actor, AuditEvent
from app.ids import IdGenerator


class AuditLog:
    """In-memory append-only log of decisions."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._ids = IdGenerator()
        self._events: list[AuditEvent] = []

    def log(
        self,
        actor: Actor,
        action: str,
        *,
        call_id: str | None = None,
        incident_id: str | None = None,
        details: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> AuditEvent:
        """Append one entry and return it."""
        event = AuditEvent(
            id=self._ids.next("audit"),
            ts=ts or datetime.now(timezone.utc),
            actor=actor,
            action=action,
            call_id=call_id,
            incident_id=incident_id,
            details=details or {},
        )
        with self._lock:
            self._events.append(event)
        return event

    def events(self, limit: int | None = None) -> list[AuditEvent]:
        """Entries oldest first, optionally only the most recent ``limit``."""
        with self._lock:
            events = list(self._events)
        return events[-limit:] if limit else events

    def for_call(self, call_id: str) -> list[AuditEvent]:
        return [event for event in self.events() if event.call_id == call_id]

    def for_incident(self, incident_id: str) -> list[AuditEvent]:
        return [event for event in self.events() if event.incident_id == incident_id]

    def reset(self) -> None:
        """Clear the log. Only used by ``POST /api/reset`` and tests."""
        with self._lock:
            self._events.clear()
            self._ids.reset()
