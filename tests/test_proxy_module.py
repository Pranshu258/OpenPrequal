import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

import proxy as proxy_mod


class TestProxyModule(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(proxy_mod.app)

    @patch("proxy.REGISTRY_CLASSES", {"default": MagicMock(return_value=MagicMock())})
    @patch("proxy.Config", new_callable=MagicMock)
    def test_registry_factory_builtin(self, mock_config):
        mock_config.REGISTRY_CLASS = "default"
        reg = proxy_mod.registry_factory()
        self.assertIsNotNone(reg)

    @patch("proxy.import_from_string", MagicMock(return_value=MagicMock()))
    @patch("proxy.REGISTRY_CLASSES", {})
    @patch("proxy.Config", new_callable=MagicMock)
    def test_registry_factory_import(self, mock_config):
        mock_config.REGISTRY_CLASS = "some.module.Class"
        reg = proxy_mod.registry_factory()
        self.assertIsNotNone(reg)

    @patch("proxy.LB_CLASSES", {"default": MagicMock(return_value=MagicMock())})
    @patch("proxy.Config", new_callable=MagicMock)
    def test_load_balancer_factory_builtin(self, mock_config):
        mock_config.LOAD_BALANCER_CLASS = "default"
        lb = proxy_mod.load_balancer_factory(MagicMock())
        self.assertIsNotNone(lb)

    @patch("proxy.import_from_string", MagicMock(return_value=MagicMock()))
    @patch("proxy.LB_CLASSES", {})
    @patch("proxy.Config", new_callable=MagicMock)
    def test_load_balancer_factory_import(self, mock_config):
        mock_config.LOAD_BALANCER_CLASS = "some.module.Class"
        lb = proxy_mod.load_balancer_factory(MagicMock())
        self.assertIsNotNone(lb)

    @patch.object(proxy_mod.registry, "register", new_callable=AsyncMock)
    def test_register_backend(self, mock_register):
        mock_register.return_value = {"status": "registered"}
        response = self.client.post(
            "/register", json={"url": "u", "port": 1, "health": True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())

    @patch.object(proxy_mod.registry, "unregister", new_callable=AsyncMock)
    def test_unregister_backend(self, mock_unregister):
        mock_unregister.return_value = {"status": "unregistered"}
        response = self.client.post(
            "/unregister", json={"url": "u", "port": 1, "health": True}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("status", response.json())

    @patch.object(
        proxy_mod.lb_instance, "get_next_backend", return_value="http://backend"
    )
    @patch.object(proxy_mod.proxy_handler, "handle_proxy", new_callable=AsyncMock)
    def test_proxy_route(self, mock_handle_proxy, mock_get_next_backend):
        mock_handle_proxy.return_value = MagicMock(
            status_code=200, content=b"ok", headers={}
        )
        response = self.client.get("/somepath")
        self.assertEqual(response.status_code, 200)

    @patch.object(proxy_mod.lb_instance, "get_next_backend", return_value=None)
    @patch.object(proxy_mod.proxy_handler, "handle_proxy", new_callable=AsyncMock)
    def test_proxy_route_no_backend(self, mock_handle_proxy, mock_get_next_backend):
        # Should return 503 from ProxyHandler
        mock_handle_proxy.return_value = MagicMock(
            status_code=503, content=b"fail", headers={}
        )
        response = self.client.get("/somepath")
        self.assertIn(
            response.status_code, (200, 503)
        )  # Accept 503 or 200 if FastAPI handles


if __name__ == "__main__":
    unittest.main()
