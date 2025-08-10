import logging
import time
from typing import List

from config.logging_config import setup_logging
from contracts.backend import Backend

setup_logging()
logger = logging.getLogger(__name__)


class BackendRegistry:
    """
    Registry for managing backend service instances and their heartbeat status.
    """

    def __init__(self, heartbeat_timeout=None):
        """
        Initialize the BackendRegistry.

        Args:
            heartbeat_timeout (Optional[int]): Timeout in seconds for backend heartbeats.
        """
        # Use a dict to ensure canonical Backend objects by (url, port)
        self._backends = {}
        self._last_heartbeat = {}  # (url, port) -> timestamp
        self.heartbeat_timeout = heartbeat_timeout
        logger.info(
            f"BackendRegistry initialized with heartbeat_timeout={self.heartbeat_timeout}"
        )

    async def register(self, backend: Backend):
        """
        Register a backend and update its last heartbeat timestamp.

        Args:
            backend (Backend): The backend instance to register.

        Returns:
            dict: Registration status and backend data.
        """
        key = (backend.url, backend.port)
        self._backends[key] = backend
        self._last_heartbeat[key] = time.time()
        logger.info(f"Registered backend: {backend}")
        # else: keep the existing object (preserve probe state)
        return {"status": "registered", "backend": self._backends[key].model_dump()}

    async def unregister(self, backend: Backend):
        """
        Unregister a backend and remove its heartbeat record.

        Args:
            backend (Backend): The backend instance to unregister.

        Returns:
            dict: Unregistration status and backend data.
        """
        key = (backend.url, backend.port)
        self._backends.pop(key, None)
        self._last_heartbeat.pop(key, None)
        logger.info(f"Unregistered backend: {backend}")
        return {"status": "unregistered", "backend": backend.model_dump()}

    def list_backends(self) -> List[Backend]:
        """
        List all registered backends, marking those with expired heartbeats as unhealthy.

        Returns:
            List[Backend]: List of backend instances.
        """
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
