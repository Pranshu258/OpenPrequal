from typing import Optional

from abstractions.load_balancer import LoadBalancer
from core.profiler import Profiler


class LeastRIFLoadBalancer(LoadBalancer):
    """
    Selects the backend with the least requests in flight (RIF).
    """

    @Profiler.profile
    def __init__(self, registry):
        self.registry = registry

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in await self.registry.list_backends() if b.health]
        if not backends:
            return None
        backend = min(backends, key=lambda b: b.in_flight_requests)
        return backend.url
