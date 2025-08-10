import unittest

from abstractions.load_balancer import LoadBalancer
from abstractions.registry import Registry
from contracts.backend import Backend


class TestLoadBalancerAbstraction(unittest.TestCase):
    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            LoadBalancer()

    def test_subclass_must_implement_get_next_backend(self):
        class DummyLB(LoadBalancer):
            def get_next_backend(self):
                return "backend"

        lb = DummyLB()
        self.assertEqual(lb.get_next_backend(), "backend")


class TestRegistryAbstraction(unittest.TestCase):
    def test_cannot_instantiate_abstract(self):
        with self.assertRaises(TypeError):
            Registry()

    def test_subclass_must_implement_methods(self):
        class DummyRegistry(Registry):
            def register(self, url, port=None, **kwargs):
                return True

            def unregister(self, url, port=None, **kwargs):
                return True

            def list_backends(self):
                return [Backend(url="u")]

        reg = DummyRegistry()
        self.assertTrue(reg.register("u"))
        self.assertTrue(reg.unregister("u"))
        self.assertEqual(reg.list_backends()[0].url, "u")


if __name__ == "__main__":
    unittest.main()
