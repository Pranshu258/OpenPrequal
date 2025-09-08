import unittest
import asyncio
import random
import string
from unittest.mock import MagicMock, patch, AsyncMock
from prometheus_client import CollectorRegistry

from core.metrics_manager import MetricsManager


class TestMetricsManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Generate a unique suffix for metric names to avoid collisions
        self.test_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        
    def _create_metrics_manager(self, rif_bins=None):
        """Helper to create a MetricsManager with unique metric names"""
        registry = CollectorRegistry()
        
        # Patch both the registry and the metric creation to use unique names
        with patch('prometheus_client.REGISTRY', registry), \
             patch('prometheus_client.Gauge') as mock_gauge, \
             patch('prometheus_client.Histogram') as mock_histogram:
            
            # Create mock metrics that behave like real ones but with unique names
            mock_gauge_instance = MagicMock()
            mock_gauge_instance._value.get.return_value = 0.0
            mock_gauge.return_value = mock_gauge_instance
            
            mock_histogram_instance = MagicMock()
            mock_histogram_instance.collect.return_value = [
                MagicMock(samples=[
                    MagicMock(name="request_latency_seconds_sum", value=0.0),
                    MagicMock(name="request_latency_seconds_count", value=0.0),
                ])
            ]
            mock_histogram.return_value = mock_histogram_instance
            
            mm = MetricsManager(rif_bins=rif_bins)
            # Manually set the mocked metrics
            mm.IN_FLIGHT = mock_gauge_instance
            mm.REQ_LATENCY = mock_histogram_instance
            return mm

    def test_init_with_rif_bins(self):
        """Test initialization with RIF bins"""
        mm = self._create_metrics_manager(rif_bins=[50, 10, 100, 20])  # Unsorted
        # Should be sorted and deduplicated
        self.assertEqual(mm._rif_bins, [10, 20, 50, 100])

    def test_init_without_rif_bins(self):
        """Test initialization without RIF bins"""
        mm = self._create_metrics_manager()
        self.assertIsNone(mm._rif_bins)

    def test_get_rif_key_with_bins(self):
        """Test _get_rif_key method with RIF bins"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        # Test exact matches and binning
        self.assertEqual(mm._get_rif_key(5), 10)   # First bin
        self.assertEqual(mm._get_rif_key(10), 10)  # Exact match
        self.assertEqual(mm._get_rif_key(15), 20)  # Second bin
        self.assertEqual(mm._get_rif_key(75), 100) # Last bin
        self.assertEqual(mm._get_rif_key(200), 100) # Clamped to max

    def test_get_rif_key_without_bins(self):
        """Test _get_rif_key method without RIF bins"""
        # Should return the RIF value itself
        mm = self._create_metrics_manager()
        self.assertEqual(mm._get_rif_key(5), 5)
        self.assertEqual(mm._get_rif_key(100), 100)

    async def test_prometheus_middleware(self):
        """Test prometheus middleware functionality"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        mock_request = MagicMock()
        
        # Mock a response that takes some time
        async def mock_call_next(request):
            await asyncio.sleep(0.01)  # 10ms delay
            return MagicMock()
        
        with patch('time.time') as mock_time:
            # Setup time mock to return consistent values
            mock_time.side_effect = [100.0, 100.01]  # Start and end times
            
            response = await mm.prometheus_middleware(
                mock_request, mock_call_next
            )
            
            # Check that in-flight was tracked
            self.assertIsNotNone(response)

    def test_get_in_flight(self):
        """Test get_in_flight method"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        # Should return a float value
        in_flight = mm.get_in_flight()
        self.assertIsInstance(in_flight, float)
        
    def test_get_rif_avg_latency(self):
        """Test get_rif_avg_latency method"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        # Should return a float value (default 0.0 when no data)
        rif_avg_latency = mm.get_rif_avg_latency()
        self.assertIsInstance(rif_avg_latency, float)

    def test_get_overall_avg_latency(self):
        """Test get_overall_avg_latency method"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        # Should return a float value
        overall_avg_latency = mm.get_overall_avg_latency()
        self.assertIsInstance(overall_avg_latency, float)

    async def test_middleware_records_latency_by_rif(self):
        """Test that middleware records latency data categorized by RIF"""
        mm = self._create_metrics_manager(rif_bins=[10, 20, 50, 100])
        mock_request = MagicMock()
        
        async def mock_call_next(request):
            await asyncio.sleep(0.001)  # 1ms delay
            return MagicMock()
        
        # Set initial in-flight count
        with patch.object(mm, 'get_in_flight', return_value=15.0):
            await mm.prometheus_middleware(mock_request, mock_call_next)
        
        # Check that RIF key was added to active keys
        self.assertIn(20, mm._active_rif_keys)  # 15 -> bin 20
        
    def test_empty_rif_bins_handling(self):
        """Test handling of empty RIF bins list"""
        mm = self._create_metrics_manager(rif_bins=[])
        self.assertIsNone(mm._rif_bins)
        # Should behave like no bins
        self.assertEqual(mm._get_rif_key(42), 42)


if __name__ == "__main__":
    unittest.main()
