import logging
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from config.logging_config import setup_logging
from contracts.backend import Backend

setup_logging()
logger = logging.getLogger(__name__)


class RoundRobinLoadBalancer(LoadBalancer):
    def __init__(self, registry):
        self.registry = registry
        self._last_index = 0
        logger.info("RoundRobinLoadBalancer initialized.")

    def get_next_backend(self) -> Optional[str]:
        # Sort by (url, port) for stable, predictable order
        backends = sorted(
            (b for b in self.registry.list_backends() if b.health),
            key=lambda b: (b.url, b.port),
        )
        if not backends:
            logger.warning("No healthy backends available for round robin.")
            return None
        backend = backends[self._last_index % len(backends)]
        self._last_index = (self._last_index + 1) % len(backends)
        logger.info(f"Selected backend (round robin): {backend.url}")
        return backend.url
