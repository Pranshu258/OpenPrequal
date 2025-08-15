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
        mock_resp.json.return_value = {"avg_latency": 0.1, "in_flight_requests": 2}
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        await self.manager.send_probe("backend_url")
        self.assertAlmostEqual(self.pool.get_current_latency("backend_url"), 0.1)
        self.assertEqual(self.pool.get_rif_values("backend_url"), [2])

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_send_probe_failure(self, mock_client):
        mock_resp = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        await self.manager.send_probe("backend_url")
        self.assertIsNone(self.pool.get_current_latency("backend_url"))


if __name__ == "__main__":
    unittest.main()
