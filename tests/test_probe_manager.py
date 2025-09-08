import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from core.probe_manager import ProbeManager
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue
from contracts.backend import Backend


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

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_consecutive_failures_tracking(self, mock_client):
        """Test that consecutive failures are tracked correctly"""
        mock_resp = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        
        backend_url = "http://backend1"
        
        # First failure
        await self.manager.send_probe(backend_url)
        self.assertEqual(self.manager._consecutive_failures.get(backend_url, 0), 1)
        
        # Second failure
        await self.manager.send_probe(backend_url)
        self.assertEqual(self.manager._consecutive_failures.get(backend_url, 0), 2)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_consecutive_failures_reset_on_success(self, mock_client):
        """Test that consecutive failures are reset when probe succeeds"""
        backend_url = "http://backend1"
        
        # Simulate failure first
        mock_resp_fail = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp_fail)
        await self.manager.send_probe(backend_url)
        self.assertEqual(self.manager._consecutive_failures.get(backend_url, 0), 1)
        
        # Then simulate success
        mock_resp_success = MagicMock(status_code=200)
        mock_resp_success.json.return_value = {
            "status": "ok",
            "avg_latency": 0.1, 
            "in_flight_requests": 2,
            "rif_avg_latency": 0.1,
            "overall_avg_latency": 0.1
        }
        client_instance.get = AsyncMock(return_value=mock_resp_success)
        await self.manager.send_probe(backend_url)
        
        # Consecutive failures should be reset
        self.assertEqual(self.manager._consecutive_failures.get(backend_url, 0), 0)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_backend_marked_unhealthy_after_threshold(self, mock_client):
        """Test that backend is marked unhealthy after consecutive failure threshold"""
        # Create a mock registry
        mock_registry = AsyncMock()
        mock_registry.mark_backend_unhealthy = AsyncMock(return_value=True)
        
        # Create manager with registry and threshold of 2
        manager = ProbeManager(self.pool, self.queue, registry=mock_registry, consecutive_failure_threshold=2)
        
        mock_resp = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        
        backend_url = "http://backend1"
        
        # First failure - should not mark unhealthy yet
        await manager.send_probe(backend_url)
        mock_registry.mark_backend_unhealthy.assert_not_called()
        
        # Second failure - should mark unhealthy
        await manager.send_probe(backend_url)
        mock_registry.mark_backend_unhealthy.assert_called_once_with(backend_url)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_exception_during_probe_counts_as_failure(self, mock_client):
        """Test that exceptions during probe requests count as failures"""
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(side_effect=Exception("Connection failed"))
        
        backend_url = "http://backend1"
        
        await self.manager.send_probe(backend_url)
        self.assertEqual(self.manager._consecutive_failures.get(backend_url, 0), 1)

    @patch("core.probe_manager.httpx.AsyncClient")
    async def test_no_registry_graceful_handling(self, mock_client):
        """Test that manager handles missing registry gracefully"""
        mock_resp = MagicMock(status_code=500)
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.get = AsyncMock(return_value=mock_resp)
        
        backend_url = "http://backend1"
        
        # Manager with no registry should not crash when threshold is reached
        manager = ProbeManager(self.pool, self.queue, registry=None, consecutive_failure_threshold=1)
        
        # This should not raise an exception
        await manager.send_probe(backend_url)
        self.assertEqual(manager._consecutive_failures.get(backend_url, 0), 1)


if __name__ == "__main__":
    unittest.main()
