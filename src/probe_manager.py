import time
from prometheus_client import Gauge, Histogram

IN_FLIGHT = Gauge('in_flight_requests', 'Number of requests in flight')
REQ_LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds')

async def prometheus_middleware(request, call_next):
    start = time.time()
    IN_FLIGHT.inc()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.time() - start
        IN_FLIGHT.dec()
        REQ_LATENCY.observe(elapsed)

def get_in_flight():
    return IN_FLIGHT._value.get()

def get_avg_latency():
    count = REQ_LATENCY._sum.get() if hasattr(REQ_LATENCY, '_sum') else 0.0
    num = REQ_LATENCY._count.get() if hasattr(REQ_LATENCY, '_count') else 0
    return (count / num) if num else 0.0
