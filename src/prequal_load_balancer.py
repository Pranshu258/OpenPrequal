from typing import Set, Optional, List
from src.load_balancer import LoadBalancer
from src.backend import Backend
import random

class PrequalLoadBalancer(LoadBalancer):
    def __init__(self):
        self.registered_backends: Set[Backend] = set()

    def register(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.add(backend)

    def unregister(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.discard(backend)

    def get_next_backend(self) -> Optional[str]:
        healthy_backends = [b for b in self.registered_backends if b.health]
        if not healthy_backends:
            return None
        # Lexicographic ordering: (avg_latency, in_flight_requests)
        min_tuple = min((b.windowed_latency, b.in_flight_requests, b.avg_latency) for b in healthy_backends)
        candidates = [b for b in healthy_backends if (b.windowed_latency, b.in_flight_requests, b.avg_latency) == min_tuple]
        print(healthy_backends)
        selected = random.choice(candidates)
        return selected.url

    def list_backends(self) -> List[dict]:
        return [
            {"url": b.url, "port": b.port, "health": b.health, "in_flight_requests": b.in_flight_requests, "avg_latency": b.avg_latency}
            for b in self.registered_backends
        ]
