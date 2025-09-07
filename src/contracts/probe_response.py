from pydantic import BaseModel


class ProbeResponse(BaseModel):
    """
    Data model representing the response from a backend health probe.
    """

    status: str
    in_flight_requests: int
    rif_avg_latency: float
    overall_avg_latency: float
