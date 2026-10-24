"""Compile the two LangGraph graphs that make up the call pipeline.

intake:  START -> extract -> verify -> END
commit:  START -> locate -> link -> weigh -> prioritize -> dispatch -> END

The split exists for one reason: intake may wait on Claude for up to the LLM
timeout, while commit mutates the shared store and must run under the
application lock. Keeping Claude outside the lock means a slow cache miss never
blocks other calls or the read API.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.flow.deps import FlowDeps
from app.flow.nodes import (
    make_dispatch_node,
    make_extract_node,
    make_link_node,
    make_locate_node,
    make_prioritize_node,
    make_verify_node,
    make_weigh_node,
)
from app.flow.state import CallFlowState

INTAKE_STAGES = ("extract", "verify")
COMMIT_STAGES = ("locate", "link", "weigh", "prioritize", "dispatch")


def _chain(stages: Sequence[tuple[str, Callable[[CallFlowState], CallFlowState]]]) -> Any:
    builder = StateGraph(CallFlowState)
    previous = START
    for name, node in stages:
        builder.add_node(name, node)
        builder.add_edge(previous, name)
        previous = name
    builder.add_edge(previous, END)
    return builder.compile()


def build_intake_graph(deps: FlowDeps) -> Any:
    return _chain([("extract", make_extract_node(deps)), ("verify", make_verify_node(deps))])


def build_commit_graph(deps: FlowDeps) -> Any:
    return _chain(
        [
            ("locate", make_locate_node(deps)),
            ("link", make_link_node(deps)),
            ("weigh", make_weigh_node(deps)),
            ("prioritize", make_prioritize_node(deps)),
            ("dispatch", make_dispatch_node(deps)),
        ]
    )
