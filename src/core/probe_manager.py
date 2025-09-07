import asyncio
import logging

import httpx
from contracts.probe_response import ProbeResponse

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
    ):
        self.probe_pool = probe_pool
        self.probe_task_queue = probe_task_queue
        self.probe_endpoint = probe_endpoint
        self._running = False
        self.semaphore = asyncio.Semaphore(max_concurrent_probes)

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
                    else:
                        logger.warning(
                            f"Probe failed for {backend_url}: status={resp.status_code}"
                        )
            except Exception as e:
                logger.error(f"Probe error for {backend_url}: {e}")

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
