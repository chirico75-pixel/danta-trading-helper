import asyncio
import json
from typing import AsyncGenerator

class SSEBroker:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    async def subscribe(self) -> AsyncGenerator[str, None]:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._queues.append(q)
        try:
            while True:
                data = await q.get()
                yield f"data: {data}\n\n"
        finally:
            try:
                self._queues.remove(q)
            except ValueError:
                pass

    async def broadcast(self, event_type: str, payload: dict):
        msg = json.dumps({"type": event_type, "data": payload})
        dead = []
        for q in list(self._queues):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            try:
                self._queues.remove(q)
            except ValueError:
                pass


broker = SSEBroker()
