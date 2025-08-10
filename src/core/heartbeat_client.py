import asyncio

import httpx

from contracts.backend import Backend
from core import probe_manager


class HeartbeatClient:
    def __init__(self, backend: Backend, proxy_url, heartbeat_interval):
        self.backend = backend
        self.proxy_url = proxy_url
        self.heartbeat_interval = heartbeat_interval
        self._task = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _heartbeat_loop(self):
        async with httpx.AsyncClient() as client:
            while self._running:
                try:
                    self.backend.avg_latency = probe_manager.get_avg_latency()
                    self.backend.windowed_latency = (
                        probe_manager.get_windowed_avg_latency()
                    )
                    self.backend.in_flight_requests = probe_manager.get_in_flight()
                    resp = await client.post(
                        f"{self.proxy_url}/register", json=self.backend.model_dump()
                    )
                    if resp.status_code == 200:
                        print(
                            f"[Heartbeat] Registered with proxy at {self.proxy_url} as {self.backend.url} with {self.backend.model_dump()}"
                        )
                    else:
                        print(f"[Heartbeat] Failed to register with proxy: {resp.text}")
                except Exception as e:
                    print(f"[Heartbeat] Error registering with proxy: {e}")
                await asyncio.sleep(self.heartbeat_interval)
