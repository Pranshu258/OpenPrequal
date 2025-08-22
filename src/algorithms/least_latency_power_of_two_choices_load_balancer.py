import random
from typing import Optional

from abstractions.load_balancer import LoadBalancer


class LeastLatencyPowerOfTwoChoicesLoadBalancer(LoadBalancer):
    """
    Selects two random healthy backends and picks the one with the least average latency.
    """

    def __init__(self, registry):
        self.registry = registry

    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in await self.registry.list_backends() if b.health]
        if not backends:
            return None
        if len(backends) == 1:
            return backends[0].url
        b1, b2 = random.sample(backends, 2)
        backend = b1 if b1.avg_latency <= b2.avg_latency else b2
        return backend.url
