import asyncio
import importlib

import httpx

from src.config import Config
from src.probe_response import ProbeResponse


class BackendProbeManager:
    def __init__(self, load_balancer, probe_interval=None):
        self.load_balancer = load_balancer
        self.probe_interval = probe_interval or int(
            getattr(Config, "PROXY_PROBE_INTERVAL", 60)
        )
        self._task = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._probe_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _probe_loop(self):
        while self._running:
            await self.probe_backends()
            await asyncio.sleep(self.probe_interval)

    async def probe_backends(self):
        async with httpx.AsyncClient() as client:
            for backend in list(self.load_balancer.registered_backends):
                try:
                    health_path = getattr(Config, "BACKEND_HEALTH_PATH", "/healthz")
                    resp = await client.get(f"{backend.url}{health_path}", timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        probe = ProbeResponse(**data)
                        backend.health = probe.status == "ok"
                        backend.in_flight_requests = getattr(
                            probe, "in_flight_requests", 0
                        )
                        backend.avg_latency = getattr(probe, "avg_latency", 0.0)
                        backend.windowed_latency = getattr(
                            probe, "windowed_latency", 0.0
                        )
                    else:
                        backend.health = False
                except Exception:
                    backend.health = False
