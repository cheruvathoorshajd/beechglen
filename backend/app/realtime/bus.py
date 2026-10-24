"""EventBus and the ``/ws/dashboard`` WebSocket.

Every state change publishes one :class:`DashboardEvent`; the frontend
refetches what changed. ``publish`` is thread-safe: it is called from request
worker threads and from the replay thread, and hands each message to the
event loop with ``call_soon_threadsafe``.

A slow client never blocks the pipeline: each subscriber has a bounded queue,
and when it is full the oldest message is dropped (the client refetches on the
next event anyway).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.contracts import DashboardEvent, EventType

logger = logging.getLogger(__name__)

SUBSCRIBER_QUEUE_SIZE = 256
HISTORY_SIZE = 200


class EventBus:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._history: deque[DashboardEvent] = deque(maxlen=HISTORY_SIZE)

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None) -> None:
        """Attach the server's event loop (done once, in the app lifespan)."""
        with self._lock:
            self._loop = loop

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    def publish(self, event_type: EventType, payload: dict[str, Any] | None = None) -> DashboardEvent:
        """Record the event and fan it out to every connected dashboard."""
        event = DashboardEvent(type=event_type, payload=payload or {}, ts=datetime.now(timezone.utc))
        message = event.model_dump_json()
        with self._lock:
            self._history.append(event)
            subscribers = list(self._subscribers)
            loop = self._loop
        if loop is None or loop.is_closed():
            return event
        for queue in subscribers:
            try:
                loop.call_soon_threadsafe(_offer, queue, message)
            except RuntimeError:  # loop closed between the check and the call
                break
        return event

    def recent(self, limit: int | None = None) -> list[DashboardEvent]:
        """Most recent events, oldest first (for tests and debugging)."""
        with self._lock:
            events = list(self._history)
        return events[-limit:] if limit else events

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()


def _offer(queue: asyncio.Queue[str], message: str) -> None:
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    queue.put_nowait(message)


router = APIRouter()


@router.websocket("/ws/dashboard")
async def dashboard(websocket: WebSocket) -> None:
    """Stream ``DashboardEvent`` JSON, one message per state change."""
    bus: EventBus = websocket.app.state.ctx.bus
    queue = bus.subscribe()  # before accept, so no event between accept and subscribe is lost
    await websocket.accept()
    receiver = asyncio.create_task(_drain(websocket))
    try:
        while True:
            getter = asyncio.create_task(queue.get())
            done, _ = await asyncio.wait({getter, receiver}, return_when=asyncio.FIRST_COMPLETED)
            if receiver in done:
                getter.cancel()
                break
            await websocket.send_text(getter.result())
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        bus.unsubscribe(queue)
        receiver.cancel()


async def _drain(websocket: WebSocket) -> None:
    """Read (and ignore) client messages; returns when the client disconnects."""
    with contextlib.suppress(WebSocketDisconnect, RuntimeError):
        while True:
            await websocket.receive_text()
