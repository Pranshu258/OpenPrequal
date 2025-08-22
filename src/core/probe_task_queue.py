import asyncio
import logging

logger = logging.getLogger(__name__)


class ProbeTaskQueue:
    @property
    def size(self):
        """Return the number of unique probe tasks in the queue."""
        return len(self._set)

    def __init__(self):
        self._set = set()
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition()

    async def add_task(self, backend_id):
        async with self._lock:
            if backend_id not in self._set:
                self._set.add(backend_id)
                async with self._not_empty:
                    self._not_empty.notify()
                logger.debug(f"Added probe task for backend {backend_id}")
            else:
                logger.debug(f"Probe task for backend {backend_id} already in set")

    async def get_task(self):
        while True:
            async with self._not_empty:
                await self._not_empty.wait_for(lambda: len(self._set) > 0)
            async with self._lock:
                if self._set:
                    backend_id = self._set.pop()
                    logger.debug(f"Got probe task for backend {backend_id}")
                    return backend_id

    def task_done(self):
        # No-op for set-based queue, kept for compatibility
        pass
