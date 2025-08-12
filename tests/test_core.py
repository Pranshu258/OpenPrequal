import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from contracts.backend import Backend
from core.backend_registry import BackendRegistry
from core.heartbeat_client import HeartbeatClient
from core.metrics_manager import MetricsManager
from core.proxy_handler import ProxyHandler


class TestBackendRegistry(unittest.TestCase):
    def setUp(self):
        self.reg = BackendRegistry(heartbeat_timeout=1)
        self.backend = Backend(url="u", port=1, health=True)

    def test_registry_add_backend(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.reg.register(self.backend))
        self.assertEqual(result["status"], "registered")
        self.assertIn(("u", 1), self.reg._backends)

    def test_registry_remove_backend(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.reg.register(self.backend))
        result = loop.run_until_complete(self.reg.unregister(self.backend))
        self.assertEqual(result["status"], "unregistered")
        self.assertNotIn(("u", 1), self.reg._backends)

    def test_list_backends_timeout_marks_unhealthy(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.reg.register(self.backend))
        # Simulate timeout
        import time

        self.reg._last_heartbeat[("u", 1)] -= 2
        backends = self.reg.list_backends()
        self.assertFalse(backends[0].health)


class TestHeartbeatClient(unittest.TestCase):
    @patch("core.heartbeat_client.httpx.AsyncClient")
    def test_heartbeat_loop_registers(self, mock_client):
        backend = Backend(url="u", port=1, health=True)
        metrics = MagicMock()
        metrics.get_avg_latency.return_value = 1.0
        metrics.get_in_flight.return_value = 1.0
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.post = AsyncMock(
            return_value=MagicMock(status_code=200, text="ok")
        )
        hb = HeartbeatClient(backend, "http://proxy", 0.01, metrics)

        async def one_iteration():
            async with mock_client():
                # Simulate one iteration of the heartbeat loop
                hb.backend.avg_latency = hb.metrics_manager.get_avg_latency()
                hb.backend.in_flight_requests = hb.metrics_manager.get_in_flight()
                await client_instance.post(
                    f"{hb.proxy_url}/register", json=hb.backend.model_dump()
                )

        import asyncio

        asyncio.run(one_iteration())
        self.assertTrue(metrics.get_avg_latency.called)
        self.assertTrue(client_instance.post.called)


class TestMetricsManager(unittest.TestCase):
    @patch("core.metrics_manager.Gauge")
    @patch("core.metrics_manager.Histogram")
    def test_metrics_collection(self, mock_histogram, mock_gauge):
        # Set up mocks to return floats
        mock_gauge_instance = MagicMock()
        mock_gauge_instance._value.get.return_value = 1.0
        mock_gauge.return_value = mock_gauge_instance

        mock_histogram_instance = MagicMock()
        # Simulate .collect() returning samples with _sum and _count
        mock_histogram_instance.collect.return_value = [
            MagicMock(
                samples=[
                    MagicMock(name="request_latency_seconds_sum", value=2.0),
                    MagicMock(name="request_latency_seconds_count", value=2.0),
                ]
            )
        ]
        mock_histogram.return_value = mock_histogram_instance

        mm = MetricsManager()
        # Simulate a request
        mm.IN_FLIGHT.inc()
        mm.IN_FLIGHT.dec()
        self.assertIsInstance(mm.get_in_flight(), float)
        self.assertIsInstance(mm.get_avg_latency(), float)


class TestProxyHandler(unittest.IsolatedAsyncioTestCase):
    async def test_proxy_handler_no_backend(self):
        handler = ProxyHandler()
        req = MagicMock()
        resp = await handler.handle_proxy(req, "path", None)
        self.assertEqual(resp.status_code, 503)

    @patch("core.proxy_handler.httpx.AsyncClient")
    async def test_proxy_handler_success(self, mock_client):
        handler = ProxyHandler()
        req = MagicMock()
        req.method = "GET"
        req.headers = {}
        req.body = AsyncMock(return_value=b"")
        req.query_params = {}
        mock_resp = MagicMock(status_code=200, content=b"ok", headers={})
        client_instance = mock_client.return_value.__aenter__.return_value
        client_instance.request = AsyncMock(return_value=mock_resp)
        resp = await handler.handle_proxy(req, "path", "http://backend")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
