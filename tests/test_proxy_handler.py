import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from core.proxy_handler import ProxyHandler


class TestProxyHandler(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.proxy_handler = ProxyHandler(self.mock_client)

    async def test_handle_proxy_with_backend(self):
        """Test proxy handling with a valid backend"""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers = {"Content-Type": "application/json"}
        mock_request.query_params = {"param": "value"}
        mock_request.body = AsyncMock(return_value=b'{"test": "data"}')
        
        # Mock the client request
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"message": "success"}'
        mock_response.headers = {"Content-Type": "application/json"}
        
        self.mock_client.request = AsyncMock(return_value=mock_response)
        
        backend_url = "http://backend:8001"
        path = "/test"
        
        response = await self.proxy_handler.handle_proxy(mock_request, path, backend_url)
        
        # Verify the response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{"message": "success"}')
        
        # Verify the client was called correctly
        self.mock_client.request.assert_called_once()

    async def test_handle_proxy_no_backend(self):
        """Test proxy handling when no backend is available"""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        backend_url = None
        path = "/test"
        
        response = await self.proxy_handler.handle_proxy(mock_request, path, backend_url)
        
        # Verify it returns 503 when no backend
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"No backend servers registered.", response.body)

    async def test_handle_proxy_backend_error(self):
        """Test proxy handling when backend returns an error"""
        mock_request = MagicMock()
        mock_request.method = "POST"
        mock_request.url.path = "/api/data"
        mock_request.headers = {"Authorization": "Bearer token"}
        mock_request.query_params = {}
        mock_request.body = AsyncMock(return_value=b'{"data": "test"}')
        
        # Mock the client to raise an exception
        import httpx
        self.mock_client.request = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
        
        backend_url = "http://backend:8001"
        path = "/api/data"
        
        response = await self.proxy_handler.handle_proxy(mock_request, path, backend_url)
        
        # Should return 502 Bad Gateway
        self.assertEqual(response.status_code, 502)
        self.assertIn(b"Upstream error", response.body)

    async def test_handle_proxy_different_methods(self):
        """Test proxy handling with different HTTP methods"""
        mock_request = MagicMock()
        mock_request.url.path = "/api/resource"
        mock_request.headers = {}
        mock_request.query_params = {}
        mock_request.body = AsyncMock(return_value=b'{}')
        
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.content = b'{"created": true}'
        mock_response.headers = {}
        
        self.mock_client.request = AsyncMock(return_value=mock_response)
        
        # Test different HTTP methods
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        for method in methods:
            with self.subTest(method=method):
                mock_request.method = method
                
                response = await self.proxy_handler.handle_proxy(
                    mock_request, "/api/resource", "http://backend:8001"
                )
                
                self.assertEqual(response.status_code, 201)
                
                # Verify the method was passed correctly
                call_args = self.mock_client.request.call_args
                self.assertEqual(call_args[0][0], method)  # method is the first positional argument

    async def test_handle_proxy_preserves_headers(self):
        """Test that proxy preserves request headers"""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        mock_request.headers = {
            "Authorization": "Bearer secret-token",
            "Content-Type": "application/json",
            "X-Custom-Header": "custom-value"
        }
        mock_request.query_params = {}
        mock_request.body = AsyncMock(return_value=b'{}')
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"data": "test"}'
        mock_response.headers = {"Content-Type": "application/json"}
        
        self.mock_client.request = AsyncMock(return_value=mock_response)
        
        await self.proxy_handler.handle_proxy(mock_request, "/test", "http://backend:8001")
        
        # Verify headers were passed to the backend
        call_args = self.mock_client.request.call_args
        passed_headers = call_args[1]["headers"]
        
        self.assertEqual(passed_headers["Authorization"], "Bearer secret-token")
        self.assertEqual(passed_headers["Content-Type"], "application/json")
        self.assertEqual(passed_headers["X-Custom-Header"], "custom-value")

    async def test_handle_proxy_with_query_params(self):
        """Test proxy handling with query parameters"""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/search"
        mock_request.headers = {}
        mock_request.query_params = {"q": "test query", "limit": "10"}
        mock_request.body = AsyncMock(return_value=b'')
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'{"results": []}'
        mock_response.headers = {}
        
        self.mock_client.request = AsyncMock(return_value=mock_response)
        
        await self.proxy_handler.handle_proxy(mock_request, "/search", "http://backend:8001")
        
        # Verify query params were preserved
        call_args = self.mock_client.request.call_args
        passed_params = call_args[1]["params"]
        
        self.assertEqual(passed_params["q"], "test query")
        self.assertEqual(passed_params["limit"], "10")

    async def test_url_construction(self):
        """Test that URLs are constructed correctly"""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/api/v1/users"
        mock_request.headers = {}
        mock_request.query_params = {}
        mock_request.body = AsyncMock(return_value=b'')
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'[]'
        mock_response.headers = {}
        
        self.mock_client.request = AsyncMock(return_value=mock_response)
        
        backend_url = "http://backend:8001"
        path = "/api/v1/users"
        
        await self.proxy_handler.handle_proxy(mock_request, path, backend_url)
        
        # Verify the URL was constructed correctly
        call_args = self.mock_client.request.call_args
        expected_url = "http://backend:8001/api/v1/users"
        self.assertEqual(call_args[0][1], expected_url)  # url is the second positional argument


if __name__ == "__main__":
    unittest.main()
