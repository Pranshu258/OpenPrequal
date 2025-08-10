import asyncio

import httpx

from src.config import Config
from src.probe_response import ProbeResponse


class BackendProbeManager:
    def __init__(self, registry):
        self.registry = registry
        self.probe_interval = int(getattr(Config, "PROXY_PROBE_INTERVAL", 30))
        self._task = None
        self._running = False

    async def start(self):
        print("[ProbeManager] start() called. Starting probe loop...")
        self._running = True
        self._task = asyncio.create_task(self._probe_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _probe_loop(self):
        print(f"[ProbeManager] Probe loop started. Interval: {self.probe_interval}s")
        while self._running:
            print("[ProbeManager] Loop tick. Probing backends...")
            await self.probe_backends()
            await asyncio.sleep(self.probe_interval)

    async def probe_backends(self):
        print("[ProbeManager] probe_backends() called.")
        async with httpx.AsyncClient() as client:
            backends = self.registry.list_backends()
            print(f"[ProbeManager] found backends: {len(backends)}")
            for backend in backends:
                print(f"[ProbeManager] Probing backend: {backend.url}")
                try:
                    health_path = getattr(Config, "BACKEND_HEALTH_PATH", "/healthz")
                    resp = await client.get(f"{backend.url}{health_path}", timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        print(f"[ProbeManager] Probe response: {data}")
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
                        print(
                            f"[ProbeManager] Probe failed for {backend.url}, status {resp.status_code}"
                        )
                        backend.health = False
                except Exception as e:
                    print(f"[ProbeManager] Exception probing {backend.url}: {e}")
                    backend.health = False
