from typing import Optional

from abstractions import registry
from abstractions.load_balancer import LoadBalancer
from core.profiler import Profiler


class LeastLatencyLoadBalancer(LoadBalancer):
    """
    Selects the backend with the least average latency.
    """

    @Profiler.profile
    def __init__(self, registry : registry.Registry):
        self.registry = registry

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in await self.registry.list_backends() if b.health]
        if not backends:
            return None
        backend = min(backends, key=lambda b: b.overall_avg_latency)
        return backend.url
