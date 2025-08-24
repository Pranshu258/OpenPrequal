import random
from typing import Optional

from abstractions.load_balancer import LoadBalancer
from core.profiler import Profiler


class RandomLoadBalancer(LoadBalancer):
    """
    Selects a healthy backend at random.
    """

    @Profiler.profile
    def __init__(self, registry):
        self.registry = registry

    @Profiler.profile
    async def get_next_backend(self) -> Optional[str]:
        backends = [b for b in await self.registry.list_backends() if b.health]
        if not backends:
            return None
        return random.choice(backends).url
