from pydantic import BaseModel

class ProbeResponse(BaseModel):
    status: str
    in_flight_requests: int
    avg_latency: float
    windowed_latency: float
