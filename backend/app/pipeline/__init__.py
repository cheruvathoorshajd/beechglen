"""Domain logic for the call pipeline.

``locate``, ``link``, ``weigh``, ``priority`` and ``dispatch`` are pure
deterministic functions: no I/O, no LLM calls, no hidden state. ``extract`` and
``verify`` are the only modules that touch the model or the cache.

Orchestration lives in :mod:`app.flow`, which wires these functions into
LangGraph nodes.
"""
