import unittest

from fastapi.testclient import TestClient

import server as server_mod


class TestServerModule(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_mod.app)

    def test_read_root(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_metrics_endpoint(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers["content-type"])

    def test_healthz_endpoint(self):
        response = self.client.get("/probe")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("in_flight_requests", data)
        self.assertIn("avg_latency", data)
        self.assertIn("windowed_latency", data)


if __name__ == "__main__":
    unittest.main()
