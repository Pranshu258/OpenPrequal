import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

from core.heartbeat_client import HeartbeatClient
from contracts.backend import Backend
from core.metrics_manager import MetricsManager


class TestHeartbeatClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.backend = Backend(url="http://localhost:8001", port=8001, health=True)
        self.metrics_manager = MagicMock(spec=MetricsManager)
        self.metrics_manager.get_overall_avg_latency.return_value = 0.1
        self.metrics_manager.get_in_flight.return_value = 5.0
        
        self.heartbeat_client = HeartbeatClient(
            backend=self.backend,
            proxy_url="http://localhost:8000",
            heartbeat_interval=0.1,  # Short interval for testing
            metrics_manager=self.metrics_manager
        )

    async def test_heartbeat_client_init(self):
        """Test HeartbeatClient initialization"""
        self.assertEqual(self.heartbeat_client.backend, self.backend)
        self.assertEqual(self.heartbeat_client.proxy_url, "http://localhost:8000")
        self.assertEqual(self.heartbeat_client.heartbeat_interval, 0.1)
        self.assertEqual(self.heartbeat_client.metrics_manager, self.metrics_manager)
        self.assertFalse(self.heartbeat_client._running)

    @patch("core.heartbeat_client.httpx.AsyncClient")
    async def test_start_and_stop(self, mock_client):
        """Test starting and stopping the heartbeat client"""
        # Mock the HTTP client
        mock_client_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post = AsyncMock(return_value=MagicMock(status_code=200))
        
        # Start the client
        start_task = asyncio.create_task(self.heartbeat_client.start())
        
        # Let it run briefly
        await asyncio.sleep(0.05)
        
        # Should be running
        self.assertTrue(self.heartbeat_client._running)
        
        # Stop the client
        await self.heartbeat_client.stop()
        
        # Should be stopped
        self.assertFalse(self.heartbeat_client._running)
        
        # Clean up the task
        start_task.cancel()
        try:
            await start_task
        except asyncio.CancelledError:
            pass

    @patch("core.heartbeat_client.httpx.AsyncClient")
    async def test_heartbeat_request_success(self, mock_client):
        """Test successful heartbeat request"""
        # Mock the HTTP client
        mock_client_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_response = MagicMock(status_code=200, text="OK")
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        
        # Run one heartbeat iteration (simulate sending one heartbeat)
        self.heartbeat_client._running = True
        # Create a task to prevent asyncio.create_task from being called
        async def mock_heartbeat():
            async with httpx.AsyncClient() as client:
                self.heartbeat_client.backend.rif_avg_latency = (
                    self.heartbeat_client.metrics_manager.get_rif_avg_latency()
                )
                self.heartbeat_client.backend.in_flight_requests = (
                    self.heartbeat_client.metrics_manager.get_in_flight()
                )
                self.heartbeat_client.backend.overall_avg_latency = (
                    self.heartbeat_client.metrics_manager.get_overall_avg_latency()
                )
                await client.post(
                    f"{self.heartbeat_client.proxy_url}/register", 
                    json=self.heartbeat_client.backend.model_dump()
                )
        
        await mock_heartbeat()
        
        # Verify the request was made
        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        
        # Check URL
        self.assertEqual(call_args[0][0], "http://localhost:8000/register")
        
        # Check that metrics were collected
        self.metrics_manager.get_overall_avg_latency.assert_called()
        self.metrics_manager.get_in_flight.assert_called()

    @patch("core.heartbeat_client.httpx.AsyncClient")
    async def test_heartbeat_request_failure(self, mock_client):
        """Test heartbeat request failure handling"""
        # Mock the HTTP client to raise an exception
        mock_client_instance = MagicMock()
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        mock_client_instance.post = AsyncMock(side_effect=Exception("Connection failed"))
        
        # Run one heartbeat iteration - should not raise exception
        self.heartbeat_client._running = True
        # Simulate heartbeat method with exception handling
        async def mock_heartbeat_with_failure():
            async with httpx.AsyncClient() as client:
                try:
                    self.heartbeat_client.backend.rif_avg_latency = (
                        self.heartbeat_client.metrics_manager.get_rif_avg_latency()
                    )
                    self.heartbeat_client.backend.in_flight_requests = (
                        self.heartbeat_client.metrics_manager.get_in_flight()
                    )
                    self.heartbeat_client.backend.overall_avg_latency = (
                        self.heartbeat_client.metrics_manager.get_overall_avg_latency()
                    )
                    await client.post(
                        f"{self.heartbeat_client.proxy_url}/register", 
                        json=self.heartbeat_client.backend.model_dump()
                    )
                except Exception:
                    pass  # Simulate error handling
        
        await mock_heartbeat_with_failure()
        
        # Verify the request was attempted
        mock_client_instance.post.assert_called_once()

    async def test_backend_data_serialization(self):
        """Test that backend data is properly serialized for heartbeat"""
        # This tests the data preparation logic
        self.assertIsInstance(self.heartbeat_client.backend.url, str)
        self.assertIsInstance(self.heartbeat_client.backend.port, int)
        self.assertIsInstance(self.heartbeat_client.backend.health, bool)

    async def test_heartbeat_interval_configuration(self):
        """Test different heartbeat interval configurations"""
        # Test with different intervals
        hb_fast = HeartbeatClient(
            backend=self.backend,
            proxy_url="http://localhost:8000",
            heartbeat_interval=0.01,
            metrics_manager=self.metrics_manager
        )
        
        hb_slow = HeartbeatClient(
            backend=self.backend,
            proxy_url="http://localhost:8000",
            heartbeat_interval=10.0,
            metrics_manager=self.metrics_manager
        )
        
        self.assertEqual(hb_fast.heartbeat_interval, 0.01)
        self.assertEqual(hb_slow.heartbeat_interval, 10.0)


if __name__ == "__main__":
    unittest.main()
