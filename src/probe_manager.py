import threading
import time

from prometheus_client import Gauge, Histogram

from src.config import Config

IN_FLIGHT = Gauge("in_flight_requests", "Number of requests in flight")
REQ_LATENCY = Histogram("request_latency_seconds", "Request latency in seconds")


# For rolling window average
_latency_samples = []  # Each entry: (timestamp, latency)
_latency_lock = threading.Lock()


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
        now = time.time()
        with _latency_lock:
            _latency_samples.append((now, elapsed))
            # Remove samples older than 5 minutes
            cutoff = now - Config.LATENCY_WINDOW_SECONDS
            while _latency_samples and _latency_samples[0][0] < cutoff:
                _latency_samples.pop(0)


def get_in_flight():
    return IN_FLIGHT._value.get()


def get_avg_latency():
    # Prometheus histogram average (since startup)
    total = 0.0
    count = 0.0
    for metric in REQ_LATENCY.collect():
        for sample in metric.samples:
            if sample.name.endswith("_sum"):
                total = sample.value
            if sample.name.endswith("_count"):
                count = sample.value
    return (total / count) if count else 0.0


def get_windowed_avg_latency():
    # Rolling 5-minute window average
    with _latency_lock:
        if not _latency_samples:
            return 0.0
        return sum(lat for _, lat in _latency_samples) / len(_latency_samples)
