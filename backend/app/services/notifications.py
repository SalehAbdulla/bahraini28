"""In-process real-time notification bus (SSE).

A lightweight publisher/subscriber used to push purchase alerts to connected
admin dashboards via Server-Sent Events. Subscribers are ``asyncio`` queues;
``publish`` fans out an SSE-formatted payload to every connected queue.

Note: this is an in-memory, single-process design appropriate for this
deployment. A production deployment with multiple workers should back this
with Redis pub/sub; the API surface is intentionally the same so that swap is
isolated inside this module.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

MAX_BUFFER = 100


class NotificationBus:
    """Async fan-out for SSE notifications."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=MAX_BUFFER)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        payload = f"event: {event}\ndata: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"
        async with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                # Slow consumers must not block publishers; drop the oldest.
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except Exception:  # pragma: no cover — defensive
                    pass

    async def on_connect_greeting(self, queue: asyncio.Queue[str]) -> None:
        try:
            queue.put_nowait("event: connected\ndata: {}\n\n")
        except asyncio.QueueFull:  # pragma: no cover
            pass


bus = NotificationBus()