import unittest

from algorithms.prequal_load_balancer import PrequalLoadBalancer
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
            avg_latency=3,
        )
        b2 = Backend(
            url="b",
            health=True,
            windowed_latency=0.5,
            in_flight_requests=1,
            avg_latency=2,
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


if __name__ == "__main__":
    unittest.main()
