import logging
import random
from statistics import median
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from config.logging_config import setup_logging
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue

setup_logging()
logger = logging.getLogger(__name__)


class PrequalLoadBalancer(LoadBalancer):
    """
    Load balancer that selects a backend based on probe pool hot/cold classification and latency/rif.
    Also manages probe task scheduling with random selection without replacement.
    """

    def __init__(
        self, registry, probe_pool: ProbePool, probe_task_queue: ProbeTaskQueue
    ):
        self._registry = registry
        self._probe_pool = probe_pool
        self._probe_task_queue = probe_task_queue
        self._probe_history = set()
        logger.info("PrequalLoadBalancer initialized.")

    def _classify_backends(self, backends):
        """Classify backends as hot or cold based on RIF values."""
        cold, hot = [], []
        for backend in backends:
            backend_id = backend.url
            rifs = self._probe_pool.get_rif_values(backend_id)
            if not rifs:
                cold.append(backend)
                continue
            current_rif = rifs[-1]
            median_rif = median(rifs)
            if current_rif < median_rif:
                cold.append(backend)
            else:
                hot.append(backend)
        return cold, hot

    def _select_backend(self, cold, hot):
        """Select backend from cold (lowest latency) or hot (lowest current rif)."""
        if cold:
            min_latency = min(
                self._probe_pool.get_current_latency(b.url) or float("inf")
                for b in cold
            )
            candidates = [
                b
                for b in cold
                if (self._probe_pool.get_current_latency(b.url) or float("inf"))
                == min_latency
            ]
            selected = random.choice(candidates)
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
        else:
            min_rif = min(
                (
                    self._probe_pool.get_rif_values(b.url)[-1]
                    if self._probe_pool.get_rif_values(b.url)
                    else float("inf")
                )
                for b in hot
            )
            candidates = [
                b
                for b in hot
                if (
                    self._probe_pool.get_rif_values(b.url)[-1]
                    if self._probe_pool.get_rif_values(b.url)
                    else float("inf")
                )
                == min_rif
            ]
            selected = random.choice(candidates)
            logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
        return selected

    async def _schedule_probe_tasks(self, healthy_backends):
        """Enqueue probe tasks for two randomly selected backends (without replacement)."""
        backend_ids = set(b.url for b in healthy_backends)
        self._probe_history &= backend_ids  # Remove history for unhealthy backends
        available = list(backend_ids - self._probe_history)
        if len(available) < 2:
            self._probe_history = set()
            available = list(backend_ids)
        probe_targets = random.sample(available, min(2, len(available)))
        for backend_id in probe_targets:
            await self._probe_task_queue.add_task(backend_id)
            self._probe_history.add(backend_id)

    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        healthy_backends = [b for b in self._registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold, hot = self._classify_backends(healthy_backends)
        selected = self._select_backend(cold, hot)
        await self._schedule_probe_tasks(healthy_backends)
        return selected.url
