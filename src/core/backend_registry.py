import time
from typing import List

from contracts.backend import Backend


class BackendRegistry:
    def __init__(self, heartbeat_timeout=None):
        # Use a dict to ensure canonical Backend objects by (url, port)
        self._backends = {}
        self._last_heartbeat = {}  # (url, port) -> timestamp
        self.heartbeat_timeout = heartbeat_timeout

    async def register(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends[key] = backend
        self._last_heartbeat[key] = time.time()
        # else: keep the existing object (preserve probe state)
        return {"status": "registered", "backend": self._backends[key].model_dump()}

    async def unregister(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends.pop(key, None)
        self._last_heartbeat.pop(key, None)
        return {"status": "unregistered", "backend": backend.model_dump()}

    def list_backends(self) -> List[Backend]:
        now = time.time()
        timeout = self.heartbeat_timeout or 10  # default 10s if not set
        for key, backend in self._backends.items():
            last = self._last_heartbeat.get(key, 0)
            if now - last > timeout:
                backend.health = False
        return list(self._backends.values())
