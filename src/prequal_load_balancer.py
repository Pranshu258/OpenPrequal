import random
from typing import List, Optional, Set

from src.backend import Backend
from src.load_balancer import LoadBalancer
from src.registry import Registry


class PrequalLoadBalancer(LoadBalancer):
    def __init__(self, registry: Registry):
        self.registry = registry

    def get_next_backend(self) -> Optional[str]:
        healthy_backends = [b for b in self.registry.list_backends() if b.health]
        if not healthy_backends:
            return None
        # Lexicographic ordering: (avg_latency, in_flight_requests)
        min_tuple = min(
            (b.windowed_latency, b.in_flight_requests, b.avg_latency)
            for b in healthy_backends
        )
        candidates = [
            b
            for b in healthy_backends
            if (b.windowed_latency, b.in_flight_requests, b.avg_latency) == min_tuple
        ]
        print(healthy_backends)
        selected = random.choice(candidates)
        return selected.url
