"""Composition root: the one place that wires the application together.

``AppContext`` owns the single GraphStore, AuditLog, application lock, flow
runner, read views, event bus, LLM assist service and scenario replay. The API
resolves it through a FastAPI dependency (``request.app.state.ctx``) and never
imports a module-level singleton, so tests build their own context with fakes.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.audit import AuditLog
from app.contracts import CallIn, ClaimStatus, Extraction
from app.flow.deps import FlowDeps
from app.flow.runner import FlowRunner
from app.graph.store import GraphStore
from app.graph.views import GraphViews
from app.llm.assist import AssistService
from app.llm.client import ToolCaller
from app.paths import SCENARIO_DIR
from app.pipeline.extract import extract as default_extract
from app.pipeline.verify import ground as default_ground
from app.realtime.bus import EventBus
from app.sim.replay import ReplayController


@dataclass
class AppContext:
    store: GraphStore
    audit: AuditLog
    lock: threading.RLock
    runner: FlowRunner
    views: GraphViews
    bus: EventBus
    assist: AssistService
    replay: ReplayController

    @classmethod
    def create(
        cls,
        *,
        extract: Callable[[CallIn], Extraction] = default_extract,
        ground: Callable[[Extraction, str], list[ClaimStatus]] = default_ground,
        tool_caller: ToolCaller | None = None,
        scenario_dir: Path = SCENARIO_DIR,
    ) -> AppContext:
        store = GraphStore()
        audit = AuditLog()
        lock = threading.RLock()
        bus = EventBus()
        runner = FlowRunner(FlowDeps(store=store, audit=audit, extract=extract, ground=ground), lock)
        return cls(
            store=store,
            audit=audit,
            lock=lock,
            runner=runner,
            views=GraphViews(store, audit, lock),
            bus=bus,
            assist=AssistService(tool_caller=tool_caller),
            replay=ReplayController(process=runner.process_call, publish=bus.publish, scenario_dir=scenario_dir),
        )

    def reset(self) -> None:
        """Stop the replay, then clear the graph, audit log and LLM caches.

        Runtime settings are kept, so "Apply & Replay" can change thresholds,
        reset and replay. The replay is stopped before taking the lock: its
        thread may be waiting for the same lock inside ``process_call``.
        """
        self.replay.reset()
        with self.lock:
            self.store.reset()
            self.audit.reset()
        self.assist.clear()
