"""Composition root: the one place that wires the application together.

``AppContext`` owns the single GraphStore, AuditLog, application lock, flow
runner and read views (plus the realtime and LLM services added by the
transport layer). The API resolves it through a FastAPI dependency and never
imports a module-level singleton, so tests build their own context with fakes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.audit import AuditLog
from app.contracts import CallIn, ClaimStatus, Extraction
from app.flow.deps import FlowDeps
from app.flow.runner import FlowRunner
from app.graph.store import GraphStore
from app.graph.views import GraphViews
from app.pipeline.extract import extract as default_extract
from app.pipeline.verify import ground as default_ground


@dataclass
class AppContext:
    store: GraphStore
    audit: AuditLog
    lock: threading.RLock
    runner: FlowRunner
    views: GraphViews

    @classmethod
    def create(
        cls,
        *,
        extract: Callable[[CallIn], Extraction] = default_extract,
        ground: Callable[[Extraction, str], list[ClaimStatus]] = default_ground,
    ) -> AppContext:
        store = GraphStore()
        audit = AuditLog()
        lock = threading.RLock()
        deps = FlowDeps(store=store, audit=audit, extract=extract, ground=ground)
        return cls(
            store=store,
            audit=audit,
            lock=lock,
            runner=FlowRunner(deps, lock),
            views=GraphViews(store, audit, lock),
        )

    def reset(self) -> None:
        """Clear the graph and the audit log. Runtime settings are kept, so
        "Apply & Replay" can change thresholds and then replay."""
        with self.lock:
            self.store.reset()
            self.audit.reset()
