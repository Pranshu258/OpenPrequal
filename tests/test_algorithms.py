import unittest

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


class DummyRegistry:
    def __init__(self, backends):
        self._backends = backends

    def list_backends(self):
        return self._backends


class TestPrequalLoadBalancer(unittest.TestCase):
    def test_balancer_selects_lowest_latency(self):
        b1 = Backend(
            url="a",
            health=True,
            windowed_latency=1,
            in_flight_requests=2,
            rif_avg_latency=3,
        )
        b2 = Backend(
            url="b",
            health=True,
            windowed_latency=0.5,
            in_flight_requests=1,
            rif_avg_latency=2,
        )
        reg = DummyRegistry([b1, b2])

        # Provide dummy probe_pool and probe_task_queue
        class DummyProbePool:
            def get_rif_values(self, backend_id):
                # Make b cold (current rif < median), a hot (current rif >= median)
                if backend_id == "a":
                    return [2, 2]  # median=2, current=2 (hot)
                else:
                    return [1, 2]  # median=1.5, current=2 (hot), but let's make b cold

            def get_current_latency(self, backend_id):
                return 1 if backend_id == "a" else 0.5

        # To ensure b is cold, set current rif < median for b
        class DummyProbePool:
            def get_rif_values(self, backend_id):
                if backend_id == "a":
                    return [2, 2]  # hot
                else:
                    return [1, 0]  # median=0.5, current=0 (cold)

            def get_current_latency(self, backend_id):
                return 1 if backend_id == "a" else 0.5

        class DummyProbeTaskQueue:
            async def add_task(self, backend_id):
                pass

        probe_pool = DummyProbePool()
        probe_task_queue = DummyProbeTaskQueue()
        lb = PrequalLoadBalancer(reg, probe_pool, probe_task_queue)
        # Should always select b2
        import asyncio

        selected = asyncio.run(lb.get_next_backend())
        self.assertEqual(selected, "b")

    def test_balancer_no_healthy(self):
        b1 = Backend(url="a", health=False)
        reg = DummyRegistry([b1])

        class DummyProbePool:
            def get_rif_values(self, backend_id):
                return []

            def get_current_latency(self, backend_id):
                return None

        class DummyProbeTaskQueue:
            async def add_task(self, backend_id):
                pass

        probe_pool = DummyProbePool()
        probe_task_queue = DummyProbeTaskQueue()
        lb = PrequalLoadBalancer(reg, probe_pool, probe_task_queue)
        import asyncio

        self.assertIsNone(asyncio.run(lb.get_next_backend()))


class TestRoundRobinLoadBalancer(unittest.TestCase):
    def test_round_robin_order(self):
        b1 = Backend(url="a", port=1, health=True)
        b2 = Backend(url="b", port=2, health=True)
        reg = DummyRegistry([b1, b2])
        lb = RoundRobinLoadBalancer(reg)
        # Sorted order: a, b
        self.assertEqual(lb.get_next_backend(), "a")
        self.assertEqual(lb.get_next_backend(), "b")
        self.assertEqual(lb.get_next_backend(), "a")

    def test_round_robin_no_healthy(self):
        b1 = Backend(url="a", port=1, health=False)
        reg = DummyRegistry([b1])
        lb = RoundRobinLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


class TestLeastRIFLoadBalancer(unittest.TestCase):
    def test_least_rif(self):
        b1 = Backend(url="a", health=True, in_flight_requests=5)
        b2 = Backend(url="b", health=True, in_flight_requests=2)
        b3 = Backend(url="c", health=True, in_flight_requests=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastRIFLoadBalancer(reg)
        self.assertEqual(lb.get_next_backend(), "b")

    def test_no_healthy(self):
        b1 = Backend(url="a", health=False, in_flight_requests=1)
        reg = DummyRegistry([b1])
        lb = LeastRIFLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


class TestLeastLatencyLoadBalancer(unittest.TestCase):
    def test_least_latency(self):
        b1 = Backend(url="a", health=True, rif_avg_latency=5)
        b2 = Backend(url="b", health=True, rif_avg_latency=2)
        b3 = Backend(url="c", health=True, rif_avg_latency=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastLatencyLoadBalancer(reg)
        self.assertEqual(lb.get_next_backend(), "b")

    def test_no_healthy(self):
        b1 = Backend(url="a", health=False, rif_avg_latency=1)
        reg = DummyRegistry([b1])
        lb = LeastLatencyLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


class TestLeastRIFPowerOfTwoChoicesLoadBalancer(unittest.TestCase):
    def test_least_rif_power_of_two(self):
        b1 = Backend(url="a", health=True, in_flight_requests=5)
        b2 = Backend(url="b", health=True, in_flight_requests=2)
        b3 = Backend(url="c", health=True, in_flight_requests=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        # Run multiple times to cover randomness
        for _ in range(10):
            selected = lb.get_next_backend()
            self.assertIn(selected, ["a", "b", "c"])

    def test_one_backend(self):
        b1 = Backend(url="a", health=True, in_flight_requests=1)
        reg = DummyRegistry([b1])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        self.assertEqual(lb.get_next_backend(), "a")

    def test_no_healthy(self):
        b1 = Backend(url="a", health=False, in_flight_requests=1)
        reg = DummyRegistry([b1])
        lb = LeastRIFPowerOfTwoChoicesLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


class TestLeastLatencyPowerOfTwoChoicesLoadBalancer(unittest.TestCase):
    def test_least_latency_power_of_two(self):
        b1 = Backend(url="a", health=True, rif_avg_latency=5)
        b2 = Backend(url="b", health=True, rif_avg_latency=2)
        b3 = Backend(url="c", health=True, rif_avg_latency=7)
        reg = DummyRegistry([b1, b2, b3])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        # Run multiple times to cover randomness
        for _ in range(10):
            selected = lb.get_next_backend()
            self.assertIn(selected, ["a", "b", "c"])

    def test_one_backend(self):
        b1 = Backend(url="a", health=True, rif_avg_latency=1)
        reg = DummyRegistry([b1])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        self.assertEqual(lb.get_next_backend(), "a")

    def test_no_healthy(self):
        b1 = Backend(url="a", health=False, rif_avg_latency=1)
        reg = DummyRegistry([b1])
        lb = LeastLatencyPowerOfTwoChoicesLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


class TestRandomLoadBalancer(unittest.TestCase):
    def test_random_backend(self):
        b1 = Backend(url="a", health=True)
        b2 = Backend(url="b", health=True)
        b3 = Backend(url="c", health=True)
        reg = DummyRegistry([b1, b2, b3])
        lb = RandomLoadBalancer(reg)
        # Run multiple times to cover randomness
        for _ in range(10):
            selected = lb.get_next_backend()
            self.assertIn(selected, ["a", "b", "c"])

    def test_one_backend(self):
        b1 = Backend(url="a", health=True)
        reg = DummyRegistry([b1])
        lb = RandomLoadBalancer(reg)
        self.assertEqual(lb.get_next_backend(), "a")

    def test_no_healthy(self):
        b1 = Backend(url="a", health=False)
        reg = DummyRegistry([b1])
        lb = RandomLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


if __name__ == "__main__":
    unittest.main()
