"""Node factories: one per README pipeline stage.

Each factory takes :class:`~app.flow.deps.FlowDeps` and returns a function
``state -> partial state``. Nodes never mutate their input state.
"""

from app.flow.nodes.dispatch import make_dispatch_node
from app.flow.nodes.extract import make_extract_node
from app.flow.nodes.link import make_link_node
from app.flow.nodes.locate import make_locate_node
from app.flow.nodes.prioritize import make_prioritize_node
from app.flow.nodes.verify import make_verify_node
from app.flow.nodes.weigh import make_weigh_node

__all__ = [
    "make_dispatch_node",
    "make_extract_node",
    "make_link_node",
    "make_locate_node",
    "make_prioritize_node",
    "make_verify_node",
    "make_weigh_node",
]
