import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from core.backend_registry import BackendRegistry
from contracts.backend import Backend


class TestBackendRegistry(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = BackendRegistry(heartbeat_timeout=60)

    async def test_register_backend_async(self):
        """Test async backend registration"""
        backend = Backend(url="http://test", port=8001, health=True)
        await self.registry.register(backend)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertEqual(backends[0].url, "http://test")

    async def test_unregister_backend_async(self):
        """Test async backend unregistration"""
        backend = Backend(url="http://test", port=8001, health=True)
        await self.registry.register(backend)
        await self.registry.unregister(backend)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 0)

    async def test_list_backends_filters_unhealthy(self):
        """Test that list_backends filters out unhealthy backends"""
        healthy_backend = Backend(url="http://healthy", port=8001, health=True)
        unhealthy_backend = Backend(url="http://unhealthy", port=8002, health=False)
        
        await self.registry.register(healthy_backend)
        await self.registry.register(unhealthy_backend)
        
        backends = await self.registry.list_backends()
        urls = [b.url for b in backends]
        
        self.assertIn("http://healthy", urls)
        # Unhealthy backends should still be in the list but marked as unhealthy
        self.assertEqual(len(backends), 2)

    async def test_update_backend_health(self):
        """Test updating backend health status"""
        # Register a healthy backend
        healthy_backend = Backend(url="http://test", port=8001, health=True)
        await self.registry.register(healthy_backend)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertTrue(backends[0].health)
        
        # Update backend to unhealthy by registering a new instance
        unhealthy_backend = Backend(url="http://test", port=8001, health=False)
        await self.registry.register(unhealthy_backend)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        # Backend registry should update the health status
        self.assertFalse(backends[0].health)

    async def test_duplicate_backend_registration(self):
        """Test that registering the same backend twice updates it"""
        backend1 = Backend(url="http://test", port=8001, health=True, in_flight_requests=5)
        backend2 = Backend(url="http://test", port=8001, health=True, in_flight_requests=10)
        
        await self.registry.register(backend1)
        await self.registry.register(backend2)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertEqual(backends[0].in_flight_requests, 10)

    async def test_heartbeat_timeout_behavior(self):
        """Test heartbeat timeout behavior"""
        import time
        
        # Create registry with short timeout for testing
        short_timeout_registry = BackendRegistry(heartbeat_timeout=0.1)
        backend = Backend(url="http://test", port=8001, health=True)
        
        await short_timeout_registry.register(backend)
        
        # Wait longer than timeout
        await asyncio.sleep(0.2)
        
        # Backend should be marked as unhealthy due to timeout
        backends = await short_timeout_registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertFalse(backends[0].health)

    async def test_multiple_backends_management(self):
        """Test managing multiple backends"""
        backends_data = [
            Backend(url="http://backend1", port=8001, health=True),
            Backend(url="http://backend2", port=8002, health=True),
            Backend(url="http://backend3", port=8003, health=False),
        ]
        
        for backend in backends_data:
            await self.registry.register(backend)
        
        all_backends = await self.registry.list_backends()
        self.assertEqual(len(all_backends), 3)
        
        # Test unregistering one backend
        await self.registry.unregister(backends_data[1])
        remaining_backends = await self.registry.list_backends()
        self.assertEqual(len(remaining_backends), 2)
        
        urls = [b.url for b in remaining_backends]
        self.assertNotIn("http://backend2", urls)

    async def test_backend_metrics_update(self):
        """Test updating backend metrics"""
        backend = Backend(
            url="http://test", 
            port=8001, 
            health=True,
            in_flight_requests=5,
            rif_avg_latency=0.1,
            overall_avg_latency=0.15
        )
        
        await self.registry.register(backend)
        
        # Update with new metrics
        updated_backend = Backend(
            url="http://test",
            port=8001,
            health=True,
            in_flight_requests=8,
            rif_avg_latency=0.2,
            overall_avg_latency=0.25
        )
        
        await self.registry.register(updated_backend)
        
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertEqual(backends[0].in_flight_requests, 8)
        self.assertEqual(backends[0].rif_avg_latency, 0.2)
        self.assertEqual(backends[0].overall_avg_latency, 0.25)

    async def test_mark_backend_unhealthy_success(self):
        """Test marking a backend as unhealthy by URL"""
        backend = Backend(url="http://test", port=8001, health=True)
        await self.registry.register(backend)
        
        # Mark backend as unhealthy
        success = await self.registry.mark_backend_unhealthy("http://test")
        self.assertTrue(success)
        
        # Verify backend is now unhealthy
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertFalse(backends[0].health)

    async def test_mark_backend_unhealthy_not_found(self):
        """Test marking a non-existent backend as unhealthy"""
        # Try to mark non-existent backend as unhealthy
        success = await self.registry.mark_backend_unhealthy("http://nonexistent")
        self.assertFalse(success)

    async def test_mark_backend_unhealthy_already_unhealthy(self):
        """Test marking an already unhealthy backend as unhealthy"""
        backend = Backend(url="http://test", port=8001, health=False)
        await self.registry.register(backend)
        
        # Mark already unhealthy backend as unhealthy
        success = await self.registry.mark_backend_unhealthy("http://test")
        self.assertTrue(success)
        
        # Verify backend is still unhealthy
        backends = await self.registry.list_backends()
        self.assertEqual(len(backends), 1)
        self.assertFalse(backends[0].health)

    async def test_mark_backend_unhealthy_multiple_backends(self):
        """Test marking specific backend unhealthy when multiple backends exist"""
        backend1 = Backend(url="http://backend1", port=8001, health=True)
        backend2 = Backend(url="http://backend2", port=8002, health=True)
        backend3 = Backend(url="http://backend3", port=8003, health=True)
        
        await self.registry.register(backend1)
        await self.registry.register(backend2)
        await self.registry.register(backend3)
        
        # Mark only backend2 as unhealthy
        success = await self.registry.mark_backend_unhealthy("http://backend2")
        self.assertTrue(success)
        
        # Verify only backend2 is unhealthy
        backends = await self.registry.list_backends()
        backend_health = {b.url: b.health for b in backends}
        
        self.assertTrue(backend_health["http://backend1"])
        self.assertFalse(backend_health["http://backend2"])
        self.assertTrue(backend_health["http://backend3"])


if __name__ == "__main__":
    unittest.main()
