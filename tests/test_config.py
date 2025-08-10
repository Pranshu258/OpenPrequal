import logging
import os
import unittest

from config import logging_config
from config.config import Config


class TestConfig(unittest.TestCase):
    def test_config_defaults(self):
        self.assertEqual(Config.PROXY_URL, "http://localhost:8000")
        self.assertEqual(Config.BACKEND_PORT, "8001")
        self.assertTrue(Config.BACKEND_URL.startswith("http://localhost:"))
        self.assertIsInstance(Config.HEARTBEAT_SECONDS, int)
        self.assertIsInstance(Config.HEARTBEAT_TIMEOUT, int)
        self.assertIsInstance(Config.LATENCY_WINDOW_SECONDS, int)
        self.assertEqual(Config.BACKEND_HEALTH_PATH, "/healthz")

    def test_config_env_override(self):
        os.environ["PROXY_URL"] = "http://test:1234"
        # Reload config class
        import importlib

        import config.config as config_mod

        importlib.reload(config_mod)
        self.assertEqual(config_mod.Config.PROXY_URL, "http://test:1234")
        del os.environ["PROXY_URL"]


class TestLoggingConfig(unittest.TestCase):
    def test_logging_setup(self):
        # Should not raise
        try:
            logging_config.setup_logging()
        except Exception as e:
            self.fail(f"setup_logging() raised {e}")
        logger = logging.getLogger()
        self.assertTrue(logger.hasHandlers())


if __name__ == "__main__":
    unittest.main()
