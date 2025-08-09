import itertools
from typing import List, Optional, Set, Union

from src.backend import Backend
from src.load_balancer import LoadBalancer


class RoundRobinLoadBalancer(LoadBalancer):
    def __init__(self):
        self.registered_backends: Set[Backend] = set()
        self.backend_iter: Optional[itertools.cycle] = None

    def update_backend_iter(self):
        healthy_backends = [b for b in self.registered_backends if b.health]
        if healthy_backends:
            self.backend_iter = itertools.cycle(healthy_backends)
        else:
            self.backend_iter = None

    def register(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.add(backend)
        self.update_backend_iter()

    def unregister(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.discard(backend)
        self.update_backend_iter()

    def get_next_backend(self) -> Optional[str]:
        if not self.backend_iter:
            return None
        # Defensive: ensure backend_iter is only over healthy backends
        for _ in range(len(self.registered_backends)):
            backend = next(self.backend_iter)
            if backend.health:
                return backend.url
        return None

    def list_backends(self) -> List[dict]:
        return [
            {"url": b.url, "port": b.port, "health": b.health}
            for b in self.registered_backends
        ]
