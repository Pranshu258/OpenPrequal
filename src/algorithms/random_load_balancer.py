import random
from typing import Optional

from abstractions.load_balancer import LoadBalancer


class RandomLoadBalancer(LoadBalancer):
    """
    Selects a healthy backend at random.
    """

    def __init__(self, registry):
        self.registry = registry

    def get_next_backend(self) -> Optional[str]:
        backends = [b for b in self.registry.list_backends() if b.health]
        if not backends:
            return None
        return random.choice(backends).url
