import unittest

from contracts.backend import Backend
from contracts.probe_response import ProbeResponse


class TestBackendContract(unittest.TestCase):
    def test_backend_fields(self):
        b = Backend(
            url="u",
            port=1,
            health=True,
            in_flight_requests=2,
            avg_latency=3,
            windowed_latency=4,
        )
        self.assertEqual(b.url, "u")
        self.assertEqual(b.port, 1)
        self.assertTrue(b.health)
        self.assertEqual(b.in_flight_requests, 2)
        self.assertEqual(b.avg_latency, 3)
        self.assertEqual(b.windowed_latency, 4)

    def test_backend_equality_and_hash(self):
        b1 = Backend(url="u", port=1)
        b2 = Backend(url="u", port=1)
        b3 = Backend(url="v", port=2)
        self.assertEqual(b1, b2)
        self.assertNotEqual(b1, b3)
        self.assertEqual(hash(b1), hash(b2))
        self.assertNotEqual(hash(b1), hash(b3))

    def test_backend_repr(self):
        b = Backend(url="u", port=1)
        s = repr(b)
        self.assertIn("Backend(url=u", s)

    def test_backend_validation(self):
        # url is required
        with self.assertRaises(Exception):
            Backend()


class TestProbeResponseContract(unittest.TestCase):
    def test_probe_response_fields(self):
        p = ProbeResponse(
            status="ok", in_flight_requests=1, avg_latency=2.0, windowed_latency=3.0
        )
        self.assertEqual(p.status, "ok")
        self.assertEqual(p.in_flight_requests, 1)
        self.assertEqual(p.avg_latency, 2.0)
        self.assertEqual(p.windowed_latency, 3.0)

    def test_probe_response_validation(self):
        # status is required
        with self.assertRaises(Exception):
            ProbeResponse()


if __name__ == "__main__":
    unittest.main()
