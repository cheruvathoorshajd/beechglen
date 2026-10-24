"""Process settings and operator-tunable runtime settings.

Two distinct notions, deliberately kept apart:

``Settings``
    Immutable process configuration read once from the environment / ``.env``.
``RuntimeSettings``
    Thresholds an operator can change while the system is running.

Both are read through accessor functions rather than imported as module globals,
so tests can override them without reaching into another module's namespace.
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.contracts import RuntimeSettings, RuntimeSettingsPatch
from app.paths import REPO_ROOT

DemoMode = Literal["cache_first", "offline"]


class Settings(BaseSettings):
    """Process configuration. Mirrors README -> "Configuration"."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: str | None = None
    demo_mode: DemoMode = "cache_first"

    claude_model_extract: str = "claude-sonnet-4-5"
    claude_model_fast: str = "claude-haiku-4-5"

    # Seed values for RuntimeSettings.
    auto_link_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    suggest_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    time_window_min: int = Field(default=30, gt=0)
    mass_event_mode: bool = False

    port: int = Field(default=8080, gt=0, le=65535)
    cors_origins: str = "http://localhost:5173"

    llm_timeout_s: float = Field(default=20.0, gt=0)
    llm_max_retries: int = Field(default=1, ge=0)

    @field_validator("anthropic_api_key", mode="after")
    @classmethod
    def _blank_key_is_none(cls, value: str | None) -> str | None:
        return value or None

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, from the comma-separated env value."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def llm_enabled(self) -> bool:
        """True when live LLM calls are both permitted and possible."""
        return self.demo_mode != "offline" and self.anthropic_api_key is not None

    def seed_runtime(self) -> RuntimeSettings:
        """Build the initial :class:`RuntimeSettings` from the environment."""
        return RuntimeSettings(
            auto_link_threshold=self.auto_link_threshold,
            suggest_threshold=self.suggest_threshold,
            time_window_min=self.time_window_min,
            mass_event_mode=self.mass_event_mode,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process settings, read once per process."""
    return Settings()


class _RuntimeSettingsHolder:
    """Thread-safe holder for the mutable runtime settings.

    Hands out copies in both directions so no caller can mutate the live object
    by accident.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._value: RuntimeSettings | None = None

    def get(self) -> RuntimeSettings:
        with self._lock:
            if self._value is None:
                self._value = get_settings().seed_runtime()
            return self._value.model_copy(deep=True)

    def update(self, patch: RuntimeSettingsPatch | RuntimeSettings) -> RuntimeSettings:
        changes = (
            patch.changes()
            if isinstance(patch, RuntimeSettingsPatch)
            else patch.model_dump(exclude_none=True)
        )
        with self._lock:
            current = self.get()
            merged = current.model_copy(update=changes)
            # Re-validate so a bad patch cannot poison the live settings.
            self._value = RuntimeSettings.model_validate(merged.model_dump())
            return self._value.model_copy(deep=True)

    def reset(self) -> RuntimeSettings:
        with self._lock:
            self._value = get_settings().seed_runtime()
            return self._value.model_copy(deep=True)


_runtime = _RuntimeSettingsHolder()


def get_runtime() -> RuntimeSettings:
    """Current runtime settings (a copy)."""
    return _runtime.get()


def update_runtime(patch: RuntimeSettingsPatch | RuntimeSettings) -> RuntimeSettings:
    """Apply a partial update and return the new runtime settings (a copy)."""
    return _runtime.update(patch)


def reset_runtime() -> RuntimeSettings:
    """Restore runtime settings to their environment seed values."""
    return _runtime.reset()
