import itertools
from typing import List, Optional, Set, Union

from registry import Registry
from src.backend import Backend
from src.load_balancer import LoadBalancer


class RoundRobinLoadBalancer(LoadBalancer):
    def __init__(self, registry: Registry):
        self.registry = registry
        self.backend_iter: Optional[itertools.cycle] = None

    def update_backend_iter(self):
        healthy_backends = [b for b in self.registry.list_backends() if b.health]
        if healthy_backends:
            self.backend_iter = itertools.cycle(healthy_backends)
        else:
            self.backend_iter = None

    def get_next_backend(self) -> Optional[str]:
        if not self.backend_iter:
            return None
        # Defensive: ensure backend_iter is only over healthy backends
        for _ in range(len(self.registry.list_backends())):
            backend = next(self.backend_iter)
            if backend.health:
                return backend.url
        return None
