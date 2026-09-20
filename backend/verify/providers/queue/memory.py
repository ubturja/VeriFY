from __future__ import annotations

import asyncio
from collections import defaultdict, deque

from verify.providers.base import Queue, QueueMessage


class InMemoryQueue(Queue):
    def __init__(self) -> None:
        self._queues: dict[str, deque[QueueMessage]] = defaultdict(deque)
        self._seq = 0

    async def send(self, queue_name: str, body: dict) -> None:
        self._seq += 1
        self._queues[queue_name].append(QueueMessage(id=str(self._seq), body=body))

    async def receive(self, queue_name: str, max_messages: int = 1) -> list[QueueMessage]:
        await asyncio.sleep(0)
        bucket = self._queues[queue_name]
        out: list[QueueMessage] = []
        for _ in range(min(max_messages, len(bucket))):
            out.append(bucket.popleft())
        return out
