#!/usr/bin/env python3
"""
Test the new is_backend_healthy method in BackendRegistry.
"""
import asyncio
import time
import unittest

from contracts.backend import Backend
from core.backend_registry import BackendRegistry


class TestBackendRegistryHealthCheck(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.registry = BackendRegistry(heartbeat_timeout=5)

    async def test_is_backend_healthy_existing_healthy(self):
        """Test health check for existing healthy backend"""
        backend = Backend(url="http://test:8001", health=True)
        await self.registry.register(backend)
        
        is_healthy = await self.registry.is_backend_healthy("http://test:8001")
        self.assertTrue(is_healthy)

    async def test_is_backend_healthy_existing_unhealthy(self):
        """Test health check for existing unhealthy backend"""
        backend = Backend(url="http://test:8001", health=False)
        await self.registry.register(backend)
        
        is_healthy = await self.registry.is_backend_healthy("http://test:8001")
        self.assertFalse(is_healthy)

    async def test_is_backend_healthy_nonexistent(self):
        """Test health check for non-existent backend"""
        is_healthy = await self.registry.is_backend_healthy("http://nonexistent:8001")
        self.assertFalse(is_healthy)

    async def test_is_backend_healthy_heartbeat_timeout(self):
        """Test that health check detects heartbeat timeout"""
        # Register a backend with a short heartbeat timeout
        registry = BackendRegistry(heartbeat_timeout=0.1)  # 100ms timeout
        backend = Backend(url="http://test:8001", health=True)
        await registry.register(backend)
        
        # Initially should be healthy
        is_healthy = await registry.is_backend_healthy("http://test:8001")
        self.assertTrue(is_healthy)
        
        # Wait for heartbeat timeout
        await asyncio.sleep(0.2)
        
        # Should now be unhealthy due to timeout
        is_healthy = await registry.is_backend_healthy("http://test:8001")
        self.assertFalse(is_healthy)

    async def test_mark_unhealthy_then_check_health(self):
        """Test marking backend unhealthy and then checking health"""
        backend = Backend(url="http://test:8001", health=True)
        await self.registry.register(backend)
        
        # Initially healthy
        is_healthy = await self.registry.is_backend_healthy("http://test:8001")
        self.assertTrue(is_healthy)
        
        # Mark unhealthy
        success = await self.registry.mark_backend_unhealthy("http://test:8001")
        self.assertTrue(success)
        
        # Should now be unhealthy
        is_healthy = await self.registry.is_backend_healthy("http://test:8001")
        self.assertFalse(is_healthy)


if __name__ == "__main__":
    unittest.main()
