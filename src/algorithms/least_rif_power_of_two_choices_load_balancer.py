import random
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from core.profiler import Profiler


class LeastRIFPowerOfTwoChoicesLoadBalancer(LoadBalancer):
    """
    Selects two random healthy backends and picks the one with the least RIF.
    """

    @Profiler.profile
    def __init__(self, registry):
        self.registry = registry

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in await self.registry.list_backends() if b.health]
        if not backends:
            return None
        if len(backends) == 1:
            return backends[0].url
        b1, b2 = random.sample(backends, 2)
        backend = b1 if b1.in_flight_requests <= b2.in_flight_requests else b2
        return backend.url
