from typing import Optional

from abstractions.load_balancer import LoadBalancer


class LeastRIFLoadBalancer(LoadBalancer):
    """
    Selects the backend with the least requests in flight (RIF).
    """

    def __init__(self, registry):
        self.registry = registry

    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in self.registry.list_backends() if b.health]
        if not backends:
            return None
        backend = min(backends, key=lambda b: b.in_flight_requests)
        return backend.url
