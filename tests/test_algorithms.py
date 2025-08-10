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
        lb = PrequalLoadBalancer(reg)
        # Should always select b2
        selected = lb.get_next_backend()
        self.assertEqual(selected, "b")

    def test_balancer_no_healthy(self):
        b1 = Backend(url="a", health=False)
        reg = DummyRegistry([b1])
        lb = PrequalLoadBalancer(reg)
        self.assertIsNone(lb.get_next_backend())


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
