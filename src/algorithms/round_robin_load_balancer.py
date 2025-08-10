from typing import Optional

from abstractions.load_balancer import LoadBalancer
from contracts.backend import Backend


class RoundRobinLoadBalancer(LoadBalancer):
    def __init__(self, registry):
        self.registry = registry
        self._last_index = 0

    def get_next_backend(self) -> Optional[str]:
        # Sort by (url, port) for stable, predictable order
        backends = sorted(
            (b for b in self.registry.list_backends() if b.health),
            key=lambda b: (b.url, b.port),
        )
        if not backends:
            return None
        backend = backends[self._last_index % len(backends)]
        self._last_index = (self._last_index + 1) % len(backends)
        return backend.url
