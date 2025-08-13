import logging
import random
from statistics import median
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from config.logging_config import setup_logging
from contracts.backend import Backend
from core.probe_pool import ProbePool

setup_logging()
logger = logging.getLogger(__name__)


class PrequalLoadBalancer(LoadBalancer):
    """
    Load balancer that selects the backend with the lowest windowed latency, in-flight requests, and average latency.
    If multiple candidates are tied, one is chosen at random.
    """

    def __init__(self, registry, probe_pool: ProbePool):
        """
        Initialize the PrequalLoadBalancer.

        Args:
            registry: The backend registry instance to use for retrieving backends.
            probe_pool: The ProbePool instance to use for probe data.
        """
        self.registry = registry
        self.probe_pool = probe_pool
        logger.info("PrequalLoadBalancer initialized.")

    def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.

        Returns:
            Optional[str]: The URL of the selected backend, or None if no healthy backend is available.
        """
        healthy_backends = [b for b in self.registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold = []
        hot = []
        for backend in healthy_backends:
            backend_id = backend.url
            rifs = self.probe_pool.get_rif_values(backend_id)
            if not rifs:
                # If no probe data, treat as cold by default
                cold.append(backend)
                continue
            current_rif = rifs[-1]
            median_rif = median(rifs)
            if current_rif < median_rif:
                cold.append(backend)
            else:
                hot.append(backend)

        if cold:
            # Choose cold backend with lowest latency
            min_latency = min(
                self.probe_pool.get_current_latency(b.url) or float("inf") for b in cold
            )
            candidates = [
                b
                for b in cold
                if (self.probe_pool.get_current_latency(b.url) or float("inf"))
                == min_latency
            ]
            selected = random.choice(candidates)
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
            return selected.url
        else:
            # Choose hot backend with lowest current rif
            min_rif = min(
                (
                    self.probe_pool.get_rif_values(b.url)[-1]
                    if self.probe_pool.get_rif_values(b.url)
                    else float("inf")
                )
                for b in hot
            )
            candidates = [
                b
                for b in hot
                if (
                    self.probe_pool.get_rif_values(b.url)[-1]
                    if self.probe_pool.get_rif_values(b.url)
                    else float("inf")
                )
                == min_rif
            ]
            selected = random.choice(candidates)
            logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
            return selected.url
