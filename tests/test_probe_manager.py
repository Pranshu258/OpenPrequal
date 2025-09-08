import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.probe_manager import ProbeManager
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue


class TestProbeManager(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = ProbePool()
        self.queue = ProbeTaskQueue()
        self.manager = ProbeManager(self.pool, self.queue)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_send_probe_success(self, mock_client):
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {
            "status": "ok",
            "avg_latency": 0.1, 
            "in_flight_requests": 2,
            "rif_avg_latency": 0.1,
            "overall_avg_latency": 0.1
        }
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        await self.manager.send_probe("backend_url")
        latencies = await self.pool.get_current_latencies(["backend_url"])
        self.assertAlmostEqual(latencies[0], 0.1)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_send_probe_failure(self, mock_client):
        mock_resp = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        await self.manager.send_probe("backend_url")
        latencies = await self.pool.get_current_latencies(["backend_url"])
        self.assertIsNone(latencies[0])


if __name__ == "__main__":
    unittest.main()
