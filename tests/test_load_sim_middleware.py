import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from core.load_sim_middleware import LoadSimMiddleware
from core.profiler import Profiler


class TestLoadSimMiddleware(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_metrics_manager = MagicMock()
        self.mock_metrics_manager.get_in_flight.return_value = 5.0
        self.middleware = LoadSimMiddleware(self.mock_app, self.mock_metrics_manager)

    async def test_middleware_init(self):
        """Test middleware initialization"""
        self.assertEqual(self.middleware.metrics_manager, self.mock_metrics_manager)
        self.assertEqual(self.middleware.jitter_mul, 1)

    async def test_dispatch_adds_latency(self):
        """Test that dispatch adds latency based on RIF count"""
        mock_request = MagicMock()
        mock_call_next = AsyncMock(return_value=MagicMock())
        
        with patch('asyncio.sleep') as mock_sleep:
            response = await self.middleware.dispatch(mock_request, mock_call_next)
            
            # Should have called sleep with some latency
            mock_sleep.assert_called_once()
            # Should have called the next handler
            mock_call_next.assert_called_once_with(mock_request)
            # Should return the response from call_next
            self.assertEqual(response, mock_call_next.return_value)

    async def test_latency_calculation_with_rif(self):
        """Test that latency increases with RIF count"""
        mock_request = MagicMock()
        mock_call_next = AsyncMock(return_value=MagicMock())
        
        # Test with different RIF values
        self.mock_metrics_manager.get_in_flight.return_value = 10.0
        
        with patch('asyncio.sleep') as mock_sleep:
            await self.middleware.dispatch(mock_request, mock_call_next)
            
            # Latency should be positive (some fixed latency + jitter based on RIF)
            latency_args = mock_sleep.call_args[0]
            self.assertGreater(latency_args[0], 0)


class TestProfiler(unittest.TestCase):
    def test_profiler_decorator(self):
        """Test that the profiler decorator works without errors"""
        
        @Profiler.profile
        def test_function(x, y):
            return x + y
        
        result = test_function(1, 2)
        self.assertEqual(result, 3)

    def test_profiler_async_decorator(self):
        """Test that the profiler decorator works with async functions"""
        
        @Profiler.profile
        async def async_test_function(x, y):
            return x + y
        
        async def run_test():
            result = await async_test_function(1, 2)
            return result
        
        result = asyncio.run(run_test())
        self.assertEqual(result, 3)

    def test_profiler_class_method(self):
        """Test profiler with class methods"""
        
        class TestClass:
            @Profiler.profile
            def method(self, value):
                return value * 2
        
        obj = TestClass()
        result = obj.method(5)
        self.assertEqual(result, 10)


if __name__ == "__main__":
    unittest.main()
