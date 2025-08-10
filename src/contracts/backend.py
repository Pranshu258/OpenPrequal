from typing import Optional

from pydantic import BaseModel


class Backend(BaseModel):
    url: str
    port: Optional[int] = None
    health: bool = False
    in_flight_requests: float = 0.0
    avg_latency: float = 0.0
    windowed_latency: float = 0.0

    def __eq__(self, other):
        if not isinstance(other, Backend):
            return False
        return self.url == other.url and self.port == other.port

    def __hash__(self):
        return hash((self.url, self.port))

    def __repr__(self):
        return (
            f"Backend(url={self.url}, port={self.port}, health={self.health}, "
            f"in_flight_requests={self.in_flight_requests}, avg_latency={self.avg_latency}, windowed_latency={self.windowed_latency})"
        )
