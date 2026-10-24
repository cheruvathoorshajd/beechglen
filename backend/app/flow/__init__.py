"""The LangGraph call pipeline (orchestration layer).

Not to be confused with :mod:`app.graph`, which is the knowledge graph.

Two compiled graphs (see builder.py):

* intake: extract -> verify. May call Claude, so it runs outside the store lock.
* commit: locate -> link -> weigh -> prioritize -> dispatch. Mutates the store,
  so the runner holds the application lock while it runs.

Every number comes from :mod:`app.pipeline`; nodes only move data between the
store and those pure functions.
"""
