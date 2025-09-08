import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

from algorithms.least_latency_load_balancer import LeastLatencyLoadBalancer
from algorithms.least_latency_power_of_two_choices_load_balancer import (
    LeastLatencyPowerOfTwoChoicesLoadBalancer,
)
from algorithms.least_rif_load_balancer import LeastRIFLoadBalancer
from algorithms.least_rif_power_of_two_choices_load_balancer import (
    LeastRIFPowerOfTwoChoicesLoadBalancer,
)
from algorithms.prequal_load_balancer import PrequalLoadBalancer
from algorithms.random_load_balancer import RandomLoadBalancer
from algorithms.round_robin_load_balancer import RoundRobinLoadBalancer
from contracts.backend import Backend
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue


class DummyRegistry:
    def __init__(self, backends):
        self._backends = backends

    async def list_backends(self):
        return self._backends


class TestPrequalLoadBalancer(unittest.IsolatedAsyncioTestCase):
    @patch('algorithms.prequal_load_balancer.asyncio.create_task')
    async def test_balancer_selects_lowest_latency(self, mock_create_task):
        # Mock the background task creation to avoid event loop issues
        mock_task = MagicMock()
        mock_create_task.return_value = mock_task
        
        b1 = Backend(url="a", health=True, rif_avg_latency=3)
        b2 = Backend(url="b", health=True, rif_avg_latency=2)
        reg = DummyRegistry([b1, b2])

        # Mock probe pool and task queue
        probe_pool = MagicMock()
        probe_pool.get_current_latencies = AsyncMock(return_value=[1.0, 0.5])
        probe_pool.get_current_temperatures = AsyncMock(return_value=["cold", "cold"])
        
        probe_task_queue = MagicMock()
        probe_task_queue.add_task = AsyncMock()

        lb = PrequalLoadBalancer(reg, probe_pool, probe_task_queue)
        selected = await lb.get_next_backend()
        self.assertEqual(selected, "b")  # Should select backend with lower latency

    @patch('algorithms.prequal_load_balancer.asyncio.create_task')
    async def test_balancer_no_healthy(self, mock_create_task):
        mock_task = MagicMock()
        mock_create_task.return_value = mock_task
        
        b1 = Backend(url="a", health=False)
        reg = DummyRegistry([b1])

        probe_pool = MagicMock()
        probe_task_queue = MagicMock()
        lb = PrequalLoadBalancer(reg, probe_pool, probe_task_queue)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestRoundRobinLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_round_robin_order(self):
        b1 = Backend(url="a", port=1, health=True)
        b2 = Backend(url="b", port=2, health=True)
        reg = DummyRegistry([b1, b2])
        lb = RoundRobinLoadBalancer(reg)
        # Sorted order: a, b
        result1 = await lb.get_next_backend()
        result2 = await lb.get_next_backend()
        result3 = await lb.get_next_backend()
        self.assertEqual(result1, "a")
        self.assertEqual(result2, "b")
        self.assertEqual(result3, "a")

    async def test_round_robin_no_healthy(self):
        b1 = Backend(url="a", port=1, health=False)
        reg = DummyRegistry([b1])
        lb = RoundRobinLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestLeastRIFLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_least_rif(self):
        b1 = Backend(url="a", health=True, in_flight_requests=5)
        b2 = Backend(url="b", health=True, in_flight_requests=2)
        b3 = Backend(url="c", health=True, in_flight_requests=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastRIFLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertEqual(result, "b")

    async def test_no_healthy(self):
        b1 = Backend(url="a", health=False, in_flight_requests=1)
        reg = DummyRegistry([b1])
        lb = LeastRIFLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestLeastLatencyLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_least_latency(self):
        b1 = Backend(url="a", health=True, overall_avg_latency=5)
        b2 = Backend(url="b", health=True, overall_avg_latency=2)
        b3 = Backend(url="c", health=True, overall_avg_latency=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastLatencyLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertEqual(result, "b")

    async def test_no_healthy(self):
        b1 = Backend(url="a", health=False, overall_avg_latency=1)
        reg = DummyRegistry([b1])
        lb = LeastLatencyLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestLeastRIFPowerOfTwoChoicesLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_least_rif_power_of_two(self):
        b1 = Backend(url="a", health=True, in_flight_requests=5)
        b2 = Backend(url="b", health=True, in_flight_requests=2)
        b3 = Backend(url="c", health=True, in_flight_requests=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        selected = await lb.get_next_backend()
        self.assertIn(selected, ["a", "b", "c"])

    async def test_one_backend(self):
        b1 = Backend(url="a", health=True, in_flight_requests=5)
        reg = DummyRegistry([b1])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertEqual(result, "a")

    async def test_no_healthy(self):
        b1 = Backend(url="a", health=False, in_flight_requests=1)
        reg = DummyRegistry([b1])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestLeastLatencyPowerOfTwoChoicesLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_least_latency_power_of_two(self):
        b1 = Backend(url="a", health=True, overall_avg_latency=5)
        b2 = Backend(url="b", health=True, overall_avg_latency=2)
        b3 = Backend(url="c", health=True, overall_avg_latency=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        selected = await lb.get_next_backend()
        self.assertIn(selected, ["a", "b", "c"])

    async def test_one_backend(self):
        b1 = Backend(url="a", health=True, overall_avg_latency=5)
        reg = DummyRegistry([b1])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertEqual(result, "a")

    async def test_no_healthy(self):
        b1 = Backend(url="a", health=False, overall_avg_latency=1)
        reg = DummyRegistry([b1])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


class TestRandomLoadBalancer(unittest.IsolatedAsyncioTestCase):
    async def test_random_backend(self):
        b1 = Backend(url="a", health=True)
        b2 = Backend(url="b", health=True)
        b3 = Backend(url="c", health=True)
        reg = DummyRegistry([b1, b2, b3])
        lb = RandomLoadBalancer(reg)
        selected = await lb.get_next_backend()
        self.assertIn(selected, ["a", "b", "c"])

    async def test_one_backend(self):
        b1 = Backend(url="a", health=True)
        reg = DummyRegistry([b1])
        lb = RandomLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertEqual(result, "a")

    async def test_no_healthy(self):
        b1 = Backend(url="a", health=False)
        reg = DummyRegistry([b1])
        lb = RandomLoadBalancer(reg)
        result = await lb.get_next_backend()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
