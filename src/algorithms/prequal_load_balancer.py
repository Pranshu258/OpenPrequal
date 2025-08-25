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
        self._request_timestamps = []  # For RPS tracking
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
        """Classify backends as hot or cold, returning RIF history map to reuse."""
        # Use pre-allocated lists to avoid repeated allocations
        backend_urls = [b.url for b in backends]

        # Fetch all RIFs concurrently and build map more efficiently
        rifs_list = await asyncio.gather(
            *[self._probe_pool.get_rif_values(url) for url in backend_urls]
        )
        rifs_map = dict(zip(backend_urls, rifs_list))

        # Pre-allocate lists with capacity hints
        cold = []
        hot = []

        # Process backends in batch to reduce loop overhead
        for backend in backends:
            url = backend.url
            rifs = rifs_map[url]

            if not rifs:
                cold.append(backend)
                continue

            count = len(rifs)
            last = rifs[-1]

            # Optimize cache lookup with tuple key
            cache_key = (count, last)
            last_info = self._rif_last_info.get(url)

            if last_info == cache_key and url in self._rif_median_cache:
                med = self._rif_median_cache[url]
            else:
                med = median(rifs)
                self._rif_median_cache[url] = med
                self._rif_last_info[url] = cache_key

            # Direct comparison without intermediate variable
            if last < med:
                cold.append(backend)
            else:
                hot.append(backend)

        return cold, hot, rifs_map

    @Profiler.profile
    async def _select_backend(self, cold, hot, rifs_map=None):
        """Select backend from cold (lowest latency) or hot (lowest current rif), reusing RIF map if provided."""
        if cold:
            # Check cache first for latencies
            now = time.time()
            cached_latencies = []
            uncached_backends = []

            for backend in cold:
                cache_time = self._latency_cache_time.get(backend.url, 0)
                if (
                    now - cache_time < self._cache_timeout
                    and backend.url in self._latency_cache
                ):
                    cached_latencies.append(self._latency_cache[backend.url])
                else:
                    cached_latencies.append(None)
                    uncached_backends.append(backend)

            # Fetch only uncached latencies
            if uncached_backends:
                fresh_latencies = await asyncio.gather(
                    *[
                        self._probe_pool.get_current_latency(b.url)
                        for b in uncached_backends
                    ]
                )

                # Update cache
                for backend, latency in zip(uncached_backends, fresh_latencies):
                    if latency is not None:
                        self._latency_cache[backend.url] = latency
                        self._latency_cache_time[backend.url] = now

                # Merge cached and fresh latencies
                uncached_idx = 0
                for i, cached_lat in enumerate(cached_latencies):
                    if cached_lat is None:
                        cached_latencies[i] = fresh_latencies[uncached_idx] or float(
                            "inf"
                        )
                        uncached_idx += 1

            # Convert None to inf for comparison
            latencies = [l if l is not None else float("inf") for l in cached_latencies]
            best = min(latencies)

            # Find all backends with best latency - use index to avoid zip overhead
            candidates = [cold[i] for i, l in enumerate(latencies) if l == best]
            selected = (
                candidates[0] if len(candidates) == 1 else random.choice(candidates)
            )
            logger.info(f"Selected cold backend (lowest latency): {selected.url}")
        else:
            # Use cached RIF values when available
            if rifs_map is not None:
                cur_rifs = [
                    (rifs_map.get(b.url, [None])[-1] or float("inf")) for b in hot
                ]
            else:
                rifs_list = await asyncio.gather(
                    *[self._probe_pool.get_rif_values(b.url) for b in hot]
                )
                cur_rifs = [vals[-1] if vals else float("inf") for vals in rifs_list]

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
        Tracks RPS using a sliding window of timestamps.
        """
        now = time.time()
        window = 1.0  # seconds
        self._request_timestamps.append(now)

        # Optimize timestamp filtering - remove from start instead of recreating list
        cutoff = now - window
        while self._request_timestamps and self._request_timestamps[0] < cutoff:
            self._request_timestamps.pop(0)

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

        # --- Probabilistic probe scheduling (existing logic) ---
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
            await asyncio.sleep(0.02)

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        # Cache healthy backends for a short time to avoid repeated registry calls
        now = time.time()
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
