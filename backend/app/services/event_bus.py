from __future__ import annotations

import asyncio

from app.models import SupervisorEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[SupervisorEvent]] = set()

    async def publish(self, event: SupervisorEvent) -> None:
        for queue in list(self._subscribers):
            await queue.put(event)

    def subscribe(self) -> asyncio.Queue[SupervisorEvent]:
        queue: asyncio.Queue[SupervisorEvent] = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[SupervisorEvent]) -> None:
        self._subscribers.discard(queue)
