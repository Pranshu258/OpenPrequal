from typing import Optional


class Backend:
    def __init__(self, url: str, port: Optional[int] = None, health: bool = False, in_flight_requests: int = 0, avg_latency: float = 0.0):
        self.url = url
        self.port = port
        self.health = health
        self.in_flight_requests = in_flight_requests
        self.avg_latency = avg_latency


    def __eq__(self, other):
        if not isinstance(other, Backend):
            return False
        return self.url == other.url and self.port == other.port


    def __hash__(self):
        return hash((self.url, self.port))


    def __repr__(self):
        return (
            f"Backend(url={self.url}, port={self.port}, health={self.health}, "
            f"in_flight_requests={self.in_flight_requests}, avg_latency={self.avg_latency})"
        )
