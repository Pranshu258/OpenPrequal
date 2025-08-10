from pydantic import BaseModel


class ProbeResponse(BaseModel):
    """
    Data model representing the response from a backend health probe.
    """

    status: str
    in_flight_requests: int
    avg_latency: float
    windowed_latency: float
