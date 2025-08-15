import unittest

from core.probe_pool import ProbePool


class TestProbePool(unittest.TestCase):
    def setUp(self):
        self.pool = ProbePool()

    def test_add_probe_and_get_latency(self):
        self.pool.add_probe("backend1", 0.5, 2)
        self.pool.add_probe("backend1", 1.0, 3)
        latency = self.pool.get_current_latency("backend1")
        self.assertAlmostEqual(latency, 0.75)

    def test_max_backends_fifo(self):
        for i in range(20):
            self.pool.add_probe(f"backend{i}", 1.0, 1)
        self.assertLessEqual(len(self.pool.probes), self.pool.max_backends)

    def test_get_rif_values(self):
        self.pool.add_probe("backend2", 0.2, 5)
        self.pool.add_probe("backend2", 0.3, 6)
        rifs = self.pool.get_rif_values("backend2")
        self.assertEqual(rifs, [5, 6])


if __name__ == "__main__":
    unittest.main()
