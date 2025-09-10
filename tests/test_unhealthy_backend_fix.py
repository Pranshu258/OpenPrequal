#!/usr/bin/env python3
"""
Simple test to verify that unhealthy backends are not routed to.
"""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from fastapi import Request

from contracts.backend import Backend
from core.proxy_handler import ProxyHandler


class TestUnhealthyBackendFix(unittest.IsolatedAsyncioTestCase):
    async def test_unhealthy_backend_rejection(self):
        """Test that proxy handler rejects requests to unhealthy backends"""
        # Create a mock registry with an unhealthy backend
        mock_registry = AsyncMock()
        mock_registry.is_backend_healthy = AsyncMock(return_value=False)
        
        # Create proxy handler with the mock registry
        mock_client = MagicMock()
        proxy_handler = ProxyHandler(mock_client, registry=mock_registry)
        
        # Create a mock request
        mock_request = MagicMock(spec=Request)
        
        # Try to proxy to the unhealthy backend
        response = await proxy_handler.handle_proxy(
            mock_request, "/test", "http://unhealthy:8001"
        )
        
        # Should return 503 and not make actual request
        self.assertEqual(response.status_code, 503)
        self.assertIn("temporarily unavailable", response.body.decode())
        
        # Verify that health check was called
        mock_registry.is_backend_healthy.assert_called_once_with("http://unhealthy:8001")
        
        # Verify that no actual HTTP request was made
        mock_client.request.assert_not_called()

    async def test_healthy_backend_passthrough(self):
        """Test that proxy handler allows requests to healthy backends"""
        # Create a mock registry with a healthy backend
        mock_registry = AsyncMock()
        mock_registry.is_backend_healthy = AsyncMock(return_value=True)
        
        # Create mock HTTP client that returns a successful response
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"Success"
        mock_response.headers = {}
        mock_client.request = AsyncMock(return_value=mock_response)
        
        # Create proxy handler
        proxy_handler = ProxyHandler(mock_client, registry=mock_registry)
        
        # Create a mock request
        mock_request = MagicMock(spec=Request)
        mock_request.method = "GET"
        mock_request.headers = {}
        mock_request.body = AsyncMock(return_value=b"")
        mock_request.query_params = {}
        
        # Try to proxy to the healthy backend
        response = await proxy_handler.handle_proxy(
            mock_request, "/test", "http://healthy:8001"
        )
        
        # Should return successful response
        self.assertEqual(response.status_code, 200)
        
        # Verify that actual HTTP request was made
        mock_client.request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
