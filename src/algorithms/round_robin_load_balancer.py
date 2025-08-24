import logging
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from config.logging_config import setup_logging
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)


class RoundRobinLoadBalancer(LoadBalancer):
    """
    Load balancer that selects backends in a round-robin fashion.
    """

    @Profiler.profile
    def __init__(self, registry):
        """
        Initialize the RoundRobinLoadBalancer.

        Args:
            registry: The backend registry instance to use for retrieving backends.
        """
        self.registry = registry
        self._last_index = 0
        logger.info("RoundRobinLoadBalancer initialized.")

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to using round-robin selection.

        Returns:
            Optional[str]: The URL of the selected backend, or None if no healthy backend is available.
        """
        # Sort by (url, port) for stable, predictable order
        backends = sorted(
            (b for b in await self.registry.list_backends() if b.health),
            key=lambda b: (b.url, b.port),
        )
        if not backends:
            logger.warning("No healthy backends available for round robin.")
            return None
        backend = backends[self._last_index % len(backends)]
        self._last_index = (self._last_index + 1) % len(backends)
        logger.info(f"Selected backend (round robin): {backend.url}")
        return backend.url
