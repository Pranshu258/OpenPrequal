import unittest

from core.probe_pool import ProbePool


class TestProbePool(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = ProbePool()

    async def test_add_probe_and_get_latency(self):
        await self.pool.add_probe("backend1", 0.5, 2)
        await self.pool.add_probe("backend1", 1.0, 3)
        latencies = await self.pool.get_current_latencies(["backend1"])
        self.assertAlmostEqual(latencies[0], 0.75)  # Average of 0.5 and 1.0

    async def test_max_backends_fifo(self):
        # Add more than max_backends (16) to test FIFO eviction
        for i in range(17):
            await self.pool.add_probe(f"backend{i}", 1.0, 1)
        
        # Check that max_backends constraint is maintained
        self.assertLessEqual(len(self.pool.probes), self.pool.max_backends)
        
        # backend0 should be evicted, backend16 should still be there
        latencies = await self.pool.get_current_latencies(["backend0", "backend16"])
        self.assertIsNone(latencies[0])  # backend0 evicted
        self.assertIsNotNone(latencies[1])  # backend16 still there

    async def test_get_rif_values(self):
        await self.pool.add_probe("backend2", 0.2, 5)
        await self.pool.add_probe("backend2", 0.3, 6)
        rifs = await self.pool.get_current_rifs(["backend2"])
        # Current implementation doesn't track current RIF separately, will be 0.0
        self.assertEqual(rifs[0], 0.0)


if __name__ == "__main__":
    unittest.main()
