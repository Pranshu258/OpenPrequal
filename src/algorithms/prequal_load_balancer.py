import asyncio
import logging
import random
import time
from typing import Optional
from collections import deque

from abstractions.load_balancer import LoadBalancer
from abstractions.registry import Registry
from config.logging_config import setup_logging
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)

# Use Profiler.profile from core.profiler for method profiling


class PrequalLoadBalancer(LoadBalancer):
    """
    Load balancer that selects a backend based on probe pool hot/cold classification and latency/rif.
    Also manages probe task scheduling with random selection without replacement.
    """

    @Profiler.profile
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
        self._request_timestamps = deque()  # For RPS tracking
        self._last_probe_time = {}  # backend_id -> last probe timestamp
        # cache for median RIF values per backend
        self._rif_median_cache = {}
        # track last RIF info (count, last_value) for cache invalidation
        self._rif_last_info = {}
        # cache for current latencies to avoid repeated async calls
        self._latency_cache = {}
        self._latency_cache_time = {}
        # cache for healthy backends to avoid repeated filtering
        self._healthy_backends_cache = None
        self._healthy_backends_cache_time = 0
        # cache timeout in seconds
        self._cache_timeout = 0.005  # 1ms cache timeout for hot path
        logger.info("PrequalLoadBalancer initialized.")
        # start background probe scheduler loop
        self._scheduler_task = asyncio.create_task(self._probe_scheduler_loop())

    @Profiler.profile
    async def _classify_backends(self, backends):
        """Classify backends as hot or cold using probe pool's temperature property"""
        backend_urls = [b.url for b in backends]
        temps = await self._probe_pool.get_current_temperatures(backend_urls)
        cold = [b for b, t in zip(backends, temps) if t == "cold"]
        hot = [b for b, t in zip(backends, temps) if t == "hot"]
        return cold, hot

    @Profiler.profile
    async def _select_backend(self, cold, hot):
        """Select backend from cold (lowest latency) or hot (lowest current rif), reusing RIF map if provided."""
        if cold:
            cold_urls = [b.url for b in cold]
            latencies = await self._probe_pool.get_current_latencies(cold_urls)
            latencies = [l if l is not None else float("inf") for l in latencies]
            best = min(latencies)
            candidates = [cold[i] for i, l in enumerate(latencies) if l == best]
            selected = (
                candidates[0] if len(candidates) == 1 else random.choice(candidates)
            )
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
        else:
            hot_urls = [b.url for b in hot]
            rifs_list = await self._probe_pool.get_current_rifs(hot_urls)
            cur_rifs = [r if r is not None else float("inf") for r in rifs_list]
            best = min(cur_rifs)
            candidates = [hot[i] for i, r in enumerate(cur_rifs) if r == best]
            selected = (
                candidates[0] if len(candidates) == 1 else random.choice(candidates)
            )
            logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
        return selected

    @Profiler.profile
    async def _schedule_probe_tasks(self, healthy_backends):
        """
        Enqueue a probe task for a random healthy backend (without replacement) with probability R=5/RPS per request.
        Also ensures that every backend is probed at least once every 30 seconds.
        Tracks RPS using a sliding window of timestamps. Sliding window is intentional because buffer counter would mess with probe probability on time boundaries.
        """
        now = time.time()
        window = 1.0  # seconds

        # Optimize timestamp filtering - remove from start instead of recreating list
        cutoff = now - window
        while self._request_timestamps and self._request_timestamps[0] < cutoff:
            self._request_timestamps.popleft()

        rps = max(len(self._request_timestamps) / window, 1e-6)  # Avoid div by zero
        R = min(5.0 / rps, 1.0)  # Cap at 1.0

        # Pre-compute backend IDs set once
        backend_ids = {b.url for b in healthy_backends}

        # Optimize set intersection
        self._probe_history.intersection_update(backend_ids)

        # --- Ensure at least one probe every 20 seconds per backend ---
        min_probe_interval = 20.0

        # Use list comprehension for forced probes
        forced_backends = [
            backend_id
            for backend_id in backend_ids
            if now - self._last_probe_time.get(backend_id, 0) >= min_probe_interval
        ]

        # Batch update timestamps and schedule tasks
        if forced_backends:
            for backend_id in forced_backends:
                self._last_probe_time[backend_id] = now
                asyncio.create_task(self._probe_task_queue.add_task(backend_id))
                logger.info(
                    f"Forced scheduled probe for backend {backend_id} (interval > 20s)"
                )

        # --- Probabilistic probe scheduling ---
        available = backend_ids - self._probe_history
        if not available:
            self._probe_history.clear()
            available = backend_ids

        if random.random() < R and available:
            # Convert to list only when needed and use faster selection
            available_list = list(available)
            backend_id = (
                available_list[0]
                if len(available_list) == 1
                else random.choice(available_list)
            )
            self._probe_history.add(backend_id)
            self._last_probe_time[backend_id] = now
            asyncio.create_task(self._probe_task_queue.add_task(backend_id))
            logger.info(
                f"Scheduled probe for backend {backend_id} (R={R:.3f}, RPS={rps:.2f})"
            )
        else:
            logger.debug(f"No probe scheduled (R={R:.3f}, RPS={rps:.2f})")

    @Profiler.profile
    async def _probe_scheduler_loop(self):
        """
        Background task to periodically invoke probe scheduling.
        """
        while True:
            backends = [b for b in await self._registry.list_backends() if b.health]
            await self._schedule_probe_tasks(backends)
            # wait before next scheduling cycle
            await asyncio.sleep(0.01)

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        # Cache healthy backends for a short time to avoid repeated registry calls
        now = time.time()
        self._request_timestamps.append(now)
        
        if (
            self._healthy_backends_cache is None
            or now - self._healthy_backends_cache_time > self._cache_timeout
        ):
            all_backends = await self._registry.list_backends()
            self._healthy_backends_cache = [b for b in all_backends if b.health]
            self._healthy_backends_cache_time = now

        healthy_backends = self._healthy_backends_cache

        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        cold, hot, rifs_map = await self._classify_backends(healthy_backends)
        selected = await self._select_backend(cold, hot, rifs_map)
        return selected.url
