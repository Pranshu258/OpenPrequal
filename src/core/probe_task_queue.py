import asyncio
import logging

logger = logging.getLogger(__name__)


class ProbeTaskQueue:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def add_task(self, backend_id):
        await self.queue.put(backend_id)

    async def get_task(self):
        return await self.queue.get()

    def task_done(self):
        self.queue.task_done()
