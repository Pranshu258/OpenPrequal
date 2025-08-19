from typing import Optional

from abstractions.load_balancer import LoadBalancer


class LeastLatencyLoadBalancer(LoadBalancer):
    """
    Selects the backend with the least average latency.
    """

    def __init__(self, registry):
        self.registry = registry

    def get_next_backend(self) -> Optional[str]:
        backends = [b for b in self.registry.list_backends() if b.health]
        if not backends:
            return None
        backend = min(backends, key=lambda b: b.avg_latency)
        return backend.url
