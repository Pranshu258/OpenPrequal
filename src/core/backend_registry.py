import asyncio
import logging
import time
from typing import List

from abstractions.registry import Registry
from config.logging_config import setup_logging
from contracts.backend import Backend
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)


class BackendRegistry(Registry):
    """
    Registry for managing backend service instances and their heartbeat status.
    """

    @Profiler.profile
    def __init__(self, heartbeat_timeout=None):
        """
        Initialize the BackendRegistry.

        Args:
            heartbeat_timeout (Optional[int]): Timeout in seconds for backend heartbeats.
        """
        # Use URL as key since it already contains host:port info
        self._backends = {}  # url -> Backend
        self._last_heartbeat = {}  # url -> timestamp
        self.heartbeat_timeout = heartbeat_timeout
        self._lock = asyncio.Lock()
        logger.info(
            f"BackendRegistry initialized with heartbeat_timeout={self.heartbeat_timeout}"
        )

    @Profiler.profile
    async def register(self, backend: Backend):
        """
        Register a backend and update its last heartbeat timestamp.

        Args:
            backend (Backend): The backend instance to register.

        Returns:
            dict: Registration status and backend data.
        """
        async with self._lock:
            self._backends[backend.url] = backend
            self._last_heartbeat[backend.url] = time.time()
            logger.info(f"Registered backend: {backend}")
            logger.debug(
                f"Current backends after register: {[str(b) + ' (health=' + str(b.health) + ')' for b in self._backends.values()]}"
            )
        return {"status": "registered", "backend": self._backends[backend.url].model_dump()}

    @Profiler.profile
    async def unregister(self, backend: Backend):
        """
        Unregister a backend and remove its heartbeat record.

        Args:
            backend (Backend): The backend instance to unregister.

        Returns:
            dict: Unregistration status and backend data.
        """
        async with self._lock:
            self._backends.pop(backend.url, None)
            self._last_heartbeat.pop(backend.url, None)
            logger.info(f"Unregistered backend: {backend}")
            logger.debug(
                f"Current backends after unregister: {[str(b) + ' (health=' + str(b.health) + ')' for b in self._backends.values()]}"
            )
        return {"status": "unregistered", "backend": backend.model_dump()}

    @Profiler.profile
    async def list_backends(self) -> List[Backend]:
        """
        List all registered backends, marking those with expired heartbeats as unhealthy.

        Returns:
            List[Backend]: List of backend instances.
        """
        async with self._lock:
            now = time.time()
            timeout = self.heartbeat_timeout or 10  # default 10s if not set
            for url, backend in self._backends.items():
                last = self._last_heartbeat.get(url, 0)
                if now - last > timeout:
                    if backend.health:
                        logger.warning(
                            f"Backend {backend} marked unhealthy due to heartbeat timeout."
                        )
                        logger.info(
                            f"Health transition: {backend} healthy -> unhealthy"
                        )
                    backend.health = False
            logger.debug(
                f"Listing backends: {[str(b) + ' (health=' + str(b.health) + ')' for b in self._backends.values()]}"
            )
            return list(self._backends.values())

    @Profiler.profile
    async def mark_backend_unhealthy(self, backend_url: str) -> bool:
        """
        Mark a specific backend as unhealthy by its URL.

        Args:
            backend_url (str): The URL of the backend to mark as unhealthy.

        Returns:
            bool: True if backend was found and marked unhealthy, False if not found.
        """
        async with self._lock:
            backend = self._backends.get(backend_url)
            if backend:
                if backend.health:  # Only log if transitioning from healthy to unhealthy
                    logger.info(f"Health transition: {backend} healthy -> unhealthy (probe failures)")
                backend.health = False
                return True
            logger.warning(f"Backend with URL {backend_url} not found in registry")
            return False

    @Profiler.profile
    async def is_backend_healthy(self, backend_url: str) -> bool:
        """
        Check if a specific backend is healthy by its URL.

        Args:
            backend_url (str): The URL of the backend to check.

        Returns:
            bool: True if backend exists and is healthy, False otherwise.
        """
        async with self._lock:
            backend = self._backends.get(backend_url)
            if not backend:
                return False
            
            return backend.health
