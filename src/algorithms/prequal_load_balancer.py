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
        
        # Cache for healthy backends to reduce registry lock contention
        self._cached_healthy_backends = []
        self._cache_timestamp = 0
        self._cache_ttl = 0.01
        
        logger.info("PrequalLoadBalancer initialized.")
        # start background probe scheduler loop
        self._scheduler_task = asyncio.create_task(self._probe_scheduler_loop())

    @Profiler.profile
    async def _classify_and_select_backend(self, backends):
        """Combined classification and selection using batch data retrieval to minimize lock contention"""
        backend_urls = [b.url for b in backends]
        
        # Single batch call to get all data with one lock acquisition
        temperatures, latencies, rifs = await self._probe_pool.get_backend_data_batch(backend_urls)
        
        # Classify backends as hot or cold
        cold = []
        hot = []
        for i, backend in enumerate(backends):
            temp = temperatures[i]
            if temp == "cold":
                cold.append((backend, latencies[i]))
            elif temp == "hot":
                hot.append((backend, rifs[i]))
        
        # Select backend
        if cold:
            # Find backends with lowest latency
            valid_cold = [(b, lat) for b, lat in cold if lat is not None]
            if valid_cold:
                best_latency = min(lat for _, lat in valid_cold)
                candidates = [b for b, lat in valid_cold if lat == best_latency]
                selected = candidates[0] if len(candidates) == 1 else random.choice(candidates)
                logger.info(f"Selected cold backend (lowest latency): {selected.url}")
                return selected
        
        if hot:
            # Find backends with lowest current rif
            valid_hot = [(b, rif) for b, rif in hot if rif is not None]
            if valid_hot:
                best_rif = min(rif for _, rif in valid_hot)
                candidates = [b for b, rif in valid_hot if rif == best_rif]
                selected = candidates[0] if len(candidates) == 1 else random.choice(candidates)
                logger.info(f"Selected hot backend (lowest current rif): {selected.url}")
                return selected
        
        # Fallback: return a random available backend
        return random.choice(backends) if backends else None

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
        R = min(50.0 / rps, 1.0)  # Cap at 1.0

        # Pre-compute backend IDs set once and reuse
        backend_ids = {b.url for b in healthy_backends}

        # Optimize set intersection - only remove non-existent backends
        if self._probe_history:
            self._probe_history &= backend_ids

        # --- Ensure at least one probe every 20 seconds per backend ---
        min_probe_interval = 20.0

        # Use set comprehension for forced probes (more efficient)
        forced_backends = {
            backend_id for backend_id in backend_ids
            if now - self._last_probe_time.get(backend_id, 0) >= min_probe_interval
        }

        # --- Probabilistic probe scheduling ---
        available = backend_ids - self._probe_history
        if not available:
            self._probe_history.clear()
            available = backend_ids

        scheduled_backends = forced_backends.copy()  # Start with forced backends
        if random.random() < R and available:
            # Use random.choice on pre-converted list only when needed
            available_list = list(available)
            backend_id = (
                available_list[0]
                if len(available_list) == 1
                else random.choice(available_list)
            )
            scheduled_backends.add(backend_id)

        # Batch update probe history and last probe time
        if not scheduled_backends:
            logger.debug(f"No probe scheduled (R={R:.3f}, RPS={rps:.2f})")
        else:
            # Batch all updates
            self._probe_history.update(scheduled_backends)
            current_time = now  # Use same timestamp for all
            for backend_id in scheduled_backends:
                asyncio.create_task(self._probe_task_queue.add_task(backend_id))
                self._last_probe_time[backend_id] = current_time
                logger.info(
                    f"Scheduled probe for backend {backend_id} (R={R:.3f}, RPS={rps:.2f})"
                )

    @Profiler.profile
    async def _get_cached_healthy_backends(self):
        """Get healthy backends with caching to reduce registry lock contention in scheduler"""
        now = time.time()
        if now - self._cache_timestamp > self._cache_ttl:
            all_backends = await self._registry.list_backends()
            self._cached_healthy_backends = [b for b in all_backends if b.health]
            self._cache_timestamp = now
        return self._cached_healthy_backends

    @Profiler.profile
    async def _probe_scheduler_loop(self):
        """
        Background task to periodically invoke probe scheduling.
        """
        while True:
            healthy_backends = await self._get_cached_healthy_backends()
            await self._schedule_probe_tasks(healthy_backends)
            # wait before next scheduling cycle
            await asyncio.sleep(0.001)

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        """
        Select the next backend to route a request to, based on probe pool hot/cold classification and latency/rif.
        Also schedules probe tasks for two randomly selected backends.
        """
        now = time.time()
        self._request_timestamps.append(now)
        
        all_backends = await self._registry.list_backends()
        healthy_backends = [b for b in all_backends if b.health]

        if not healthy_backends:
            logger.warning("No healthy backends available for prequal load balancer.")
            return None

        selected = await self._classify_and_select_backend(healthy_backends)
        return selected.url if selected else None
