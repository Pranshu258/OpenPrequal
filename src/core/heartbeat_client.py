import asyncio
import logging

import httpx

from config.logging_config import setup_logging
from contracts.backend import Backend
from core.metrics_manager import MetricsManager

setup_logging()
logger = logging.getLogger(__name__)


class HeartbeatClient:
    """
    Client for sending periodic heartbeat signals to the proxy to register backend health and metrics.
    """

    def __init__(
        self,
        backend: Backend,
        proxy_url,
        heartbeat_interval,
        metrics_manager: MetricsManager,
    ):
        """
        Initialize the HeartbeatClient.

        Args:
            backend (Backend): The backend instance to report.
            proxy_url (str): The proxy URL to send heartbeats to.
            heartbeat_interval (int): Interval in seconds between heartbeats.
            metrics_manager (MetricsManager): Metrics manager for backend stats.
        """
        self.backend = backend
        self.proxy_url = proxy_url
        self.heartbeat_interval = heartbeat_interval
        self.metrics_manager = metrics_manager
        self._task = None
        self._running = False
        logger.info(f"HeartbeatClient initialized for backend {self.backend.url}")

    async def start(self):
        """
        Start the heartbeat loop as an asynchronous task.
        """
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info("Heartbeat loop started.")

    async def stop(self):
        """
        Stop the heartbeat loop and cancel the running task.
        """
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Heartbeat loop stopped.")

    async def _heartbeat_loop(self):
        """
        Internal loop that sends heartbeat data to the proxy at regular intervals.
        """
        async with httpx.AsyncClient() as client:
            while self._running:
                try:
                    self.backend.rif_avg_latency = (
                        self.metrics_manager.get_rif_avg_latency()
                    )
                    self.backend.in_flight_requests = (
                        self.metrics_manager.get_in_flight()
                    )
                    self.backend.overall_avg_latency = (
                        self.metrics_manager.get_overall_avg_latency()
                    )
                    resp = await client.post(
                        f"{self.proxy_url}/register", json=self.backend.model_dump()
                    )
                    if resp.status_code == 200:
                        logger.info(
                            f"[Heartbeat] Registered with proxy at {self.proxy_url} as {self.backend.url} with {self.backend.model_dump()}"
                        )
                    else:
                        logger.warning(
                            f"[Heartbeat] Failed to register with proxy: {resp.text}"
                        )
                except Exception as e:
                    logger.error(f"[Heartbeat] Error registering with proxy: {e}")
                await asyncio.sleep(self.heartbeat_interval)
