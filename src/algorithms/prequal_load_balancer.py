import asyncio
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
        self._last_probe_time = {}  # backend_id -> last probe timestamp
        logger.info("PrequalLoadBalancer initialized.")

    async def _classify_backends(self, backends):
        """Classify backends as hot or cold based on RIF values in parallel."""
        # fetch all RIFs concurrently
        rif_tasks = [self._probe_pool.get_rif_values(b.url) for b in backends]
        rifs_list = await asyncio.gather(*rif_tasks)
        cold, hot = [], []
        for backend, rifs in zip(backends, rifs_list):
            if not rifs:
                cold.append(backend)
                continue
            curr, med = rifs[-1], median(rifs)
            (cold if curr < med else hot).append(backend)
        return cold, hot

    async def _select_backend(self, cold, hot):
        """Select backend from cold (lowest latency) or hot (lowest current rif)."""
        if cold:
            # fetch latencies concurrently
            lat_tasks = [self._probe_pool.get_current_latency(b.url) for b in cold]
            raw = await asyncio.gather(*lat_tasks)
            latencies = [l if l is not None else float("inf") for l in raw]
            best = min(latencies)
            candidates = [b for b, l in zip(cold, latencies) if l == best]
            selected = random.choice(candidates)
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
        else:
            # fetch current RIFs concurrently
            rif_tasks = [self._probe_pool.get_rif_values(b.url) for b in hot]
            rifs_list = await asyncio.gather(*rif_tasks)
            cur_rifs = [vals[-1] if vals else float("inf") for vals in rifs_list]
            best = min(cur_rifs)
            candidates = [b for b, r in zip(hot, cur_rifs) if r == best]
            selected = random.choice(candidates)
            logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
        return selected

    async def _schedule_probe_tasks(self, healthy_backends):
        """
        Enqueue a probe task for a random healthy backend (without replacement) with probability R=5/RPS per request.
        Also ensures that every backend is probed at least once every 30 seconds.
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
        # --- Ensure at least one probe every 20 seconds per backend ---
        min_probe_interval = 20.0
        # forced probes: schedule once then update timestamps
        forced = []
        for backend_id in backend_ids:
            if now - self._last_probe_time.get(backend_id, 0) >= min_probe_interval:
                forced.append(backend_id)
                self._last_probe_time[backend_id] = now
        for backend_id in forced:
            asyncio.create_task(self._probe_task_queue.add_task(backend_id))
            logger.info(
                f"Forced scheduled probe for backend {backend_id} (interval > 20s)"
            )
        # --- Probabilistic probe scheduling (existing logic) ---
        available = list(backend_ids - self._probe_history)
        if not available:
            self._probe_history = set()
            available = list(backend_ids)
        if random.random() < R and available:
            backend_id = random.choice(available)
            self._probe_history.add(backend_id)
            self._last_probe_time[backend_id] = now
            asyncio.create_task(self._probe_task_queue.add_task(backend_id))
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
        healthy_backends = [b for b in await self._registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold, hot = await self._classify_backends(healthy_backends)
        selected = await self._select_backend(cold, hot)
        # Schedule probe tasks in background without blocking
        asyncio.create_task(self._schedule_probe_tasks(healthy_backends))
        return selected.url
