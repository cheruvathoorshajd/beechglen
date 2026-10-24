"""Shared test setup.

Tests are deterministic and never touch the network (steering: tech.md). The
real ``.env`` holds an API key, so offline mode is forced through environment
variables before any ``app`` module reads its settings; environment variables
take precedence over ``.env`` in pydantic-settings.
"""

from __future__ import annotations

import os

os.environ["DEMO_MODE"] = "offline"
os.environ["ANTHROPIC_API_KEY"] = ""

import pytest  # noqa: E402

from app.config import get_settings, reset_runtime  # noqa: E402


@pytest.fixture(autouse=True)
def _offline_settings():
    """Fresh offline settings and default runtime thresholds for every test."""
    get_settings.cache_clear()
    reset_runtime()
    assert not get_settings().llm_enabled
    yield
    get_settings.cache_clear()
    reset_runtime()
