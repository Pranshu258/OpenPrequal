import logging
import random
from typing import List, Optional, Set

from abstractions.load_balancer import LoadBalancer
from abstractions.registry import Registry
from config.logging_config import setup_logging
from contracts.backend import Backend

setup_logging()
logger = logging.getLogger(__name__)


class PrequalLoadBalancer(LoadBalancer):
    """
    Load balancer that selects the backend with the lowest windowed latency, in-flight requests, and average latency.
    If multiple candidates are tied, one is chosen at random.
    """

    def __init__(self, registry):
        """
        Initialize the PrequalLoadBalancer.

        Args:
            registry: The backend registry instance to use for retrieving backends.
        """
        self.registry = registry
        logger.info("PrequalLoadBalancer initialized.")

    def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on lowest windowed latency, in-flight requests, and average latency.

        Returns:
            Optional[str]: The URL of the selected backend, or None if no healthy backend is available.
        """
        healthy_backends = [b for b in self.registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None
        # Lexicographic ordering: (in_flight_requests, avg_latency)
        min_tuple = min((b.in_flight_requests, b.avg_latency) for b in healthy_backends)
        candidates = [
            b
            for b in healthy_backends
            if (b.in_flight_requests, b.avg_latency) == min_tuple
        ]
        logger.debug(f"Healthy backends: {healthy_backends}")
        selected = random.choice(candidates)
        logger.info(f"Selected backend (prequal): {selected.url}")
        return selected.url
