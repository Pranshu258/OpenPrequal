import asyncio
import logging

from core.profiler import Profiler

logger = logging.getLogger(__name__)


class ProbeTaskQueue:
    @property
    @Profiler.profile
    def size(self):
        """Return the number of unique probe tasks in the queue."""
        return len(self._set)

    @Profiler.profile
    def __init__(self):
        self._set = set()
        self._queue = asyncio.Queue()

    @Profiler.profile
    async def add_task(self, backend_id):
        if backend_id not in self._set:
            self._set.add(backend_id)
            await self._queue.put(backend_id)
            logger.debug(f"Added probe task for backend {backend_id}")
        else:
            logger.debug(f"Probe task for backend {backend_id} already in set")

    @Profiler.profile
    async def get_task(self):
        backend_id = await self._queue.get()
        self._set.discard(backend_id)
        logger.debug(f"Got probe task for backend {backend_id}")
        return backend_id

    @Profiler.profile
    def task_done(self):
        # No-op for set-based queue, kept for compatibility
        pass
