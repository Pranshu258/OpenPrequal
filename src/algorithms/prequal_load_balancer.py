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
        # cache for median RIF values per backend
        self._rif_median_cache = {}
        # track last RIF info (count, last_value) for cache invalidation
        self._rif_last_info = {}
        logger.info("PrequalLoadBalancer initialized.")
        # start background probe scheduler loop
        self._scheduler_task = asyncio.create_task(self._probe_scheduler_loop())

    async def _classify_backends(self, backends):
        """Classify backends as hot or cold, returning RIF history map to reuse."""
        # fetch all RIFs concurrently and build map
        rif_tasks = [self._probe_pool.get_rif_values(b.url) for b in backends]
        rifs_list = await asyncio.gather(*rif_tasks)
        rifs_map = {b.url: rifs for b, rifs in zip(backends, rifs_list)}
        cold, hot = [], []
        for backend in backends:
            rifs = rifs_map[backend.url]
            if not rifs:
                cold.append(backend)
                continue
            count, last = len(rifs), rifs[-1]
            # check cache validity
            last_info = self._rif_last_info.get(backend.url)
            if last_info == (count, last) and backend.url in self._rif_median_cache:
                med = self._rif_median_cache[backend.url]
            else:
                med = median(rifs)
                self._rif_median_cache[backend.url] = med
                self._rif_last_info[backend.url] = (count, last)
            curr = last
            (cold if curr < med else hot).append(backend)
        return cold, hot, rifs_map

    async def _select_backend(self, cold, hot, rifs_map=None):
        """Select backend from cold (lowest latency) or hot (lowest current rif), reusing RIF map if provided."""
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
            # reuse RIF values from previous classification if available
            if rifs_map is not None:
                cur_rifs = [
                    rifs_map.get(b.url, [None])[-1] or float("inf") for b in hot
                ]
            else:
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

    async def _probe_scheduler_loop(self):
        """
        Background task to periodically invoke probe scheduling.
        """
        while True:
            backends = [b for b in await self._registry.list_backends() if b.health]
            await self._schedule_probe_tasks(backends)
            # wait before next scheduling cycle
            await asyncio.sleep(0.02)

    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        healthy_backends = [b for b in await self._registry.list_backends() if b.health]
        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold, hot, rifs_map = await self._classify_backends(healthy_backends)
        selected = await self._select_backend(cold, hot, rifs_map)
        return selected.url
