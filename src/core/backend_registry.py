import logging
import time
from typing import List

from config.logging_config import setup_logging
from contracts.backend import Backend

setup_logging()
logger = logging.getLogger(__name__)


class BackendRegistry:
    def __init__(self, heartbeat_timeout=None):
        # Use a dict to ensure canonical Backend objects by (url, port)
        self._backends = {}
        self._last_heartbeat = {}  # (url, port) -> timestamp
        self.heartbeat_timeout = heartbeat_timeout
        logger.info(
            f"BackendRegistry initialized with heartbeat_timeout={self.heartbeat_timeout}"
        )

    async def register(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends[key] = backend
        self._last_heartbeat[key] = time.time()
        logger.info(f"Registered backend: {backend}")
        # else: keep the existing object (preserve probe state)
        return {"status": "registered", "backend": self._backends[key].model_dump()}

    async def unregister(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends.pop(key, None)
        self._last_heartbeat.pop(key, None)
        logger.info(f"Unregistered backend: {backend}")
        return {"status": "unregistered", "backend": backend.model_dump()}

    def list_backends(self) -> List[Backend]:
        now = time.time()
        timeout = self.heartbeat_timeout or 10  # default 10s if not set
        for key, backend in self._backends.items():
            last = self._last_heartbeat.get(key, 0)
            if now - last > timeout:
                if backend.health:
                    logger.warning(
                        f"Backend {backend} marked unhealthy due to heartbeat timeout."
                    )
                backend.health = False
        logger.debug(f"Listing backends: {list(self._backends.values())}")
        return list(self._backends.values())
