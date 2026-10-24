"""Entry points the API layer calls: process, confirm and split.

``process_call`` runs the intake graph (may call Claude) without the lock, then
the commit graph under the application lock. ``confirm_link`` and
``split_call`` are operator overrides: deterministic, audited, and followed by
a full recompute of every affected incident.
"""

from __future__ import annotations

import threading
from typing import Any

from app.contracts import CallIn, LinkDecision, ProcessResult
from app.flow import ops
from app.flow.builder import build_commit_graph, build_intake_graph
from app.flow.deps import FlowDeps
from app.pipeline import priority as prio


class LinkActionError(ValueError):
    """An operator action that does not apply to this call (HTTP 409)."""


class FlowRunner:
    def __init__(self, deps: FlowDeps, lock: threading.RLock | None = None) -> None:
        self.deps = deps
        self.lock = lock or threading.RLock()
        self._intake: Any = build_intake_graph(deps)
        self._commit: Any = build_commit_graph(deps)

    # -- calls --------------------------------------------------------------

    def process_call(self, call: CallIn) -> ProcessResult:
        """Run the seven-stage pipeline. Never drops the call."""
        state = self._intake.invoke({"call": ops.normalize_call(call)})
        with self.lock:
            final = self._commit.invoke(state)
        return final["result"]

    # -- operator overrides -------------------------------------------------

    def confirm_link(self, call_id: str) -> ProcessResult:
        """Operator confirms a suggested (or automatic) link."""
        with self.lock:
            store = self.deps.store
            call = store.require_call(call_id)
            if call.link is None or call.link.band == "new":
                raise LinkActionError("Only a call linked to an existing incident can be confirmed")
            if call.link.band == "confirmed":
                return self._result(call_id)

            previous = call.link
            decision = previous.model_copy(update={"band": "confirmed", "decided_by": "operator"})
            store.attach(call_id, decision)
            at = ops.sim_now(store)
            ops.recompute_incident(self.deps, decision.incident_id, at, call_id)
            if call.queue_item is not None:
                store.set_queue_item(call_id, call.queue_item.model_copy(update={"band": "confirmed"}))
            ops.add_timeline(store, decision.incident_id, at, "Operator confirmed link", call_id)
            self.deps.audit.log(
                "operator",
                "link.confirmed",
                call_id=call_id,
                incident_id=decision.incident_id,
                details={"previous_band": previous.band, "p_same": previous.p_same},
            )
            return self._result(call_id)

    def split_call(self, call_id: str) -> ProcessResult:
        """Operator splits a call into a new incident; both incidents recompute."""
        with self.lock:
            store = self.deps.store
            call = store.require_call(call_id)
            if call.link is None:
                raise LinkActionError("Call is not linked to an incident")
            old_id = call.link.incident_id
            if len(store.calls_for_incident(old_id)) <= 1:
                raise LinkActionError("Call is already the only call in its incident")

            extraction = call.extraction
            incident = store.create_incident(
                incident_type=extraction.incident_type,
                severity=prio.severity(extraction.incident_type, extraction.flags),
                location=call.location,
                flags=extraction.flags,
                at=call.received_at,
            )
            previous = call.link
            decision = LinkDecision(
                call_id=call_id,
                incident_id=incident.id,
                p_same=previous.p_same,
                band="new",
                components=previous.components,
                gates=[*previous.gates, "operator_split"],
                decided_by="operator",
            )
            store.attach(call_id, decision)

            at = ops.sim_now(store)
            ops.recompute_incident(self.deps, old_id, at, None)
            ops.recompute_incident(self.deps, incident.id, call.received_at, call_id)

            severity = prio.severity(extraction.incident_type, extraction.flags)
            value = prio.priority(severity, "new", 0.0, 1.0, ["new_incident"])
            if call.queue_item is not None:
                store.set_queue_item(
                    call_id,
                    call.queue_item.model_copy(
                        update={
                            "incident_id": incident.id,
                            "band": "new",
                            "novelty": 1.0,
                            "priority": prio.to_display(value),
                            "new_info": True,
                            "override_reasons": ["new_incident"],
                        }
                    ),
                )
            ops.add_timeline(store, old_id, at, f"Operator split {call_id} into {incident.id}", call_id)
            ops.add_timeline(store, incident.id, call.received_at, f"Created by operator split from {old_id}", call_id)
            self.deps.audit.log(
                "operator",
                "link.split",
                call_id=call_id,
                incident_id=incident.id,
                details={"from_incident": old_id, "to_incident": incident.id, "previous_band": previous.band},
            )
            return self._result(call_id)

    # -- helpers ------------------------------------------------------------

    def _result(self, call_id: str) -> ProcessResult:
        store = self.deps.store
        call = store.require_call(call_id)
        assert call.link is not None and call.queue_item is not None
        return ProcessResult(
            incident_id=call.link.incident_id,
            queue_item=call.queue_item,
            link=call.link,
            claims=store.claims_for_call(call_id),
        )
