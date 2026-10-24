"""Scenario replay with a simulated clock (README F13).

Each call is received at ``start_time + t_offset_s``. The replay thread sleeps
the offset difference divided by ``speed``, runs the call through the pipeline
in-process, and publishes ``call.processed`` plus a ``sim.status`` event (with
``t_offset_s`` and ``sim_time``) after every call.

A failing call is logged and skipped; it never stops the replay.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app.contracts import CallIn, ProcessResult, SimStatus
from app.paths import SCENARIO_DIR
from app.realtime.bus import call_processed_payload

logger = logging.getLogger(__name__)

_SCENARIO_ID = re.compile(r"^[a-z0-9_]{1,64}$")
_CALL_FIELDS = (
    "transcript",
    "channel",
    "caller_hash",
    "caller_role_hint",
    "device_lat",
    "device_lng",
    "psap_id",
    "transferred_from",
    "truth_incident",
    "truth_new_info",
)


class ScenarioNotFound(LookupError):
    """Unknown or invalid scenario id (HTTP 404)."""


@dataclass(frozen=True)
class ScenarioCall:
    scenario_call_id: str
    t_offset_s: float
    call: CallIn


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    title: str
    start_time: datetime
    calls: tuple[ScenarioCall, ...]


def load_scenario(scenario_id: str, scenario_dir: Path = SCENARIO_DIR) -> Scenario:
    """Parse ``data/scenarios/<scenario_id>.json`` into ready-to-send calls."""
    if not _SCENARIO_ID.match(scenario_id):
        raise ScenarioNotFound(scenario_id)
    path = scenario_dir / f"{scenario_id}.json"
    if not path.is_file():
        raise ScenarioNotFound(scenario_id)
    payload = json.loads(path.read_text(encoding="utf-8"))
    start = datetime.fromisoformat(payload["start_time"])
    calls = []
    for raw in sorted(payload["calls"], key=lambda item: float(item["t_offset_s"])):
        offset = float(raw["t_offset_s"])
        fields = {key: raw[key] for key in _CALL_FIELDS if key in raw}
        call = CallIn(**fields, received_at=start + timedelta(seconds=offset), scenario_id=scenario_id)
        calls.append(ScenarioCall(scenario_call_id=str(raw["id"]), t_offset_s=offset, call=call))
    return Scenario(
        scenario_id=scenario_id,
        title=str(payload.get("title", scenario_id)),
        start_time=start,
        calls=tuple(calls),
    )


def list_scenarios(scenario_dir: Path = SCENARIO_DIR) -> list[str]:
    return sorted(p.stem for p in scenario_dir.glob("*.json") if _SCENARIO_ID.match(p.stem))


class ReplayController:
    """Runs at most one scenario replay at a time on a background thread."""

    def __init__(
        self,
        *,
        process: Callable[[CallIn], ProcessResult],
        publish: Callable[[str, dict[str, Any]], Any],
        scenario_dir: Path = SCENARIO_DIR,
    ) -> None:
        self._process = process
        self._publish = publish
        self._scenario_dir = scenario_dir
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._status = SimStatus()

    # -- control ------------------------------------------------------------

    def start(self, scenario_id: str, speed: float) -> SimStatus:
        scenario = load_scenario(scenario_id, self._scenario_dir)
        self.stop(publish=False)
        stop = threading.Event()
        status = SimStatus(
            scenario_id=scenario_id,
            running=True,
            speed=speed,
            t_offset_s=0.0,
            sim_time=scenario.start_time,
            calls_sent=0,
            calls_total=len(scenario.calls),
        )
        thread = threading.Thread(
            target=self._run, args=(scenario, speed, stop), name=f"replay-{scenario_id}", daemon=True
        )
        with self._lock:
            self._stop = stop
            self._status = status
            self._thread = thread
        self._emit_status()
        thread.start()
        return status

    def stop(self, *, publish: bool = True) -> SimStatus:
        with self._lock:
            thread, stop = self._thread, self._stop
            was_running = self._status.running
        stop.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=10)
        with self._lock:
            self._status = self._status.model_copy(update={"running": False})
            self._thread = None
            status = self._status
        if publish and was_running:
            self._emit_status()
        return status

    def reset(self) -> SimStatus:
        """Stop and forget the replay (part of POST /api/reset)."""
        self.stop(publish=False)
        with self._lock:
            self._status = SimStatus()
            return self._status

    def status(self) -> SimStatus:
        with self._lock:
            return self._status

    def sim_time(self) -> datetime | None:
        """Latest simulated time of the current or last replay (for live chat)."""
        with self._lock:
            return self._status.sim_time if self._status.calls_sent else None

    def join(self, timeout: float | None = None) -> None:
        """Wait for the replay thread to finish (tests and the evaluation)."""
        with self._lock:
            thread = self._thread
        if thread is not None:
            thread.join(timeout)

    # -- worker -------------------------------------------------------------

    def _run(self, scenario: Scenario, speed: float, stop: threading.Event) -> None:
        previous = 0.0
        try:
            for index, item in enumerate(scenario.calls):
                if stop.wait(max(0.0, (item.t_offset_s - previous) / speed)):
                    return
                previous = item.t_offset_s
                try:
                    result = self._process(item.call)
                except Exception:  # noqa: BLE001 - one bad call never stops the replay
                    logger.exception("Replay call %s failed", item.scenario_call_id)
                    continue
                with self._lock:
                    if stop.is_set():
                        return
                    self._status = self._status.model_copy(
                        update={
                            "t_offset_s": item.t_offset_s,
                            "sim_time": item.call.received_at,
                            "calls_sent": index + 1,
                        }
                    )
                self._publish(
                    "call.processed",
                    call_processed_payload(
                        result,
                        scenario_id=scenario.scenario_id,
                        scenario_call_id=item.scenario_call_id,
                    ),
                )
                self._emit_status()
        finally:
            with self._lock:
                finished = self._thread is threading.current_thread() or self._thread is None
                if finished:
                    self._status = self._status.model_copy(update={"running": False})
            if finished and not stop.is_set():
                self._emit_status()

    def _emit_status(self) -> None:
        self._publish("sim.status", self.status().model_dump(mode="json"))
