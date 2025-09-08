import asyncio
import logging

import httpx
from contracts.probe_response import ProbeResponse
from abstractions.registry import Registry
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue
from core.profiler import Profiler

logger = logging.getLogger(__name__)


class ProbeManager:
    @Profiler.profile
    def __init__(
        self,
        probe_pool: ProbePool,
        probe_task_queue: ProbeTaskQueue,
        probe_endpoint: str = "/probe",
        max_concurrent_probes: int = 20,  # Increased default concurrency
        registry: Registry = None,  # Optional backend registry for health management
        consecutive_failure_threshold: int = 3,  # Number of consecutive failures before marking unhealthy
    ):
        self.probe_pool = probe_pool
        self.probe_task_queue = probe_task_queue
        self.probe_endpoint = probe_endpoint
        self._running = False
        self.semaphore = asyncio.Semaphore(max_concurrent_probes)
        self.registry = registry
        self.consecutive_failure_threshold = consecutive_failure_threshold
        # Track consecutive failures per backend
        self._consecutive_failures = {}  # backend_url -> failure_count

    @Profiler.profile
    async def send_probe(self, backend_url: str):
        async with self.semaphore:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{backend_url}{self.probe_endpoint}", timeout=5.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        parsed = ProbeResponse.model_validate(data)
                        latency = float(parsed.rif_avg_latency)
                        rif = float(parsed.in_flight_requests)
                        await self.probe_pool.add_probe(backend_url, latency, rif)
                        logger.info(
                            f"Probe success for {backend_url}: rif_avg_latency={latency}, in_flight_requests={rif}"
                        )
                        logger.info(f"Probe rif_avg_latency for {backend_url}: {latency}")
                        # Reset consecutive failure count on successful probe
                        self._consecutive_failures.pop(backend_url, None)
                    else:
                        logger.warning(
                            f"Probe failed for {backend_url}: status={resp.status_code}"
                        )
                        await self._handle_probe_failure(backend_url)
            except Exception as e:
                logger.error(f"Probe error for {backend_url}: {e}")
                await self._handle_probe_failure(backend_url)

    async def _handle_probe_failure(self, backend_url: str):
        """Handle probe failure by tracking consecutive failures and marking backend unhealthy if threshold is exceeded."""
        self._consecutive_failures[backend_url] = self._consecutive_failures.get(backend_url, 0) + 1
        failure_count = self._consecutive_failures[backend_url]
        
        logger.warning(f"Backend {backend_url} has {failure_count} consecutive probe failures")
        
        if failure_count >= self.consecutive_failure_threshold and self.registry:
            await self.registry.mark_backend_unhealthy(backend_url)
            logger.warning(f"Backend {backend_url} marked unhealthy after {failure_count} consecutive probe failures")

    @Profiler.profile
    async def run(self):
        self._running = True
        while self._running:
            # Log the deduplicated probe task queue size
            queue_size = self.probe_task_queue.size
            logger.info(f"Probe task queue size: {queue_size}")
            backend_url = await self.probe_task_queue.get_task()
            await self.send_probe(backend_url)
            self.probe_task_queue.task_done()

    @Profiler.profile
    def stop(self):
        self._running = False
