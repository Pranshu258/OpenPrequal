import logging
import random
import time
from statistics import median
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from abstractions.registry import Registry
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
        self,
        registry: Registry,
        probe_pool: ProbePool,
        probe_task_queue: ProbeTaskQueue,
    ):
        self._registry = registry
        self._probe_pool = probe_pool
        self._probe_task_queue = probe_task_queue
        self._probe_history = set()
        self._request_timestamps = []  # For RPS tracking
        logger.info("PrequalLoadBalancer initialized.")

    async def _classify_backends(self, backends):
        """Classify backends as hot or cold based on RIF values."""
        cold, hot = [], []
        for backend in backends:
            backend_id = backend.url
            rifs = await self._probe_pool.get_rif_values(backend_id)
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

    async def _select_backend(self, cold, hot):
        """Select backend from cold (lowest latency) or hot (lowest current rif)."""
        if cold:
            latencies = []
            for b in cold:
                latency = await self._probe_pool.get_current_latency(b.url)
                latencies.append(latency if latency is not None else float("inf"))
            min_latency = min(latencies)
            candidates = [
                b for b, latency in zip(cold, latencies) if latency == min_latency
            ]
            selected = random.choice(candidates)
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
        else:
            rifs = []
            for b in hot:
                vals = await self._probe_pool.get_rif_values(b.url)
                rifs.append(vals[-1] if vals else float("inf"))
            min_rif = min(rifs)
            candidates = [b for b, rif in zip(hot, rifs) if rif == min_rif]
            selected = random.choice(candidates)
            logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
        return selected

    async def _schedule_probe_tasks(self, healthy_backends):
        """
        Enqueue a probe task for a random healthy backend (without replacement) with probability R=50/RPS per request.
        Tracks RPS using a sliding window of timestamps.
        """
        now = time.time()
        window = 1.0  # seconds
        self._request_timestamps.append(now)
        # Remove timestamps outside the window
        self._request_timestamps = [
            t for t in self._request_timestamps if now - t < window
        ]
        rps = max(len(self._request_timestamps) / window, 1e-6)  # Avoid div by zero
        R = 5.0 / rps
        R = min(R, 1.0)  # Cap at 1.0
        backend_ids = set(b.url for b in healthy_backends)
        self._probe_history &= backend_ids  # Remove history for unhealthy backends
        available = list(backend_ids - self._probe_history)
        if not available:
            self._probe_history = set()
            available = list(backend_ids)
        if random.random() < R and available:
            backend_id = random.choice(available)
            await self._probe_task_queue.add_task(backend_id)
            self._probe_history.add(backend_id)
            logger.info(
                f"Scheduled probe for backend {backend_id} (R={R:.3f}, RPS={rps:.2f})"
            )
        else:
            logger.debug(f"No probe scheduled (R={R:.3f}, RPS={rps:.2f})")

    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        healthy_backends = [b for b in self._registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold, hot = await self._classify_backends(healthy_backends)
        selected = await self._select_backend(cold, hot)
        await self._schedule_probe_tasks(healthy_backends)
        return selected.url
