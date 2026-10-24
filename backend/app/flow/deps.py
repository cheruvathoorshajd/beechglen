"""Explicit dependencies for the flow nodes (no node reads a module global)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.audit import AuditLog
from app.config import get_runtime
from app.contracts import CallIn, ClaimStatus, Extraction, RuntimeSettings
from app.graph.store import GraphStore
from app.reference import ReferenceData, reference_data


@dataclass(frozen=True)
class FlowDeps:
    """Everything a node may touch. Tests build one with fakes."""

    store: GraphStore
    audit: AuditLog
    extract: Callable[[CallIn], Extraction]
    ground: Callable[[Extraction, str], list[ClaimStatus]]
    reference: Callable[[], ReferenceData] = reference_data
    runtime: Callable[[], RuntimeSettings] = get_runtime
