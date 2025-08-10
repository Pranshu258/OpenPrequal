import logging
import threading
import time

from prometheus_client import Gauge, Histogram

from config.config import Config
from config.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)


class MetricsManager:
    def __init__(self):
        self.IN_FLIGHT = Gauge("in_flight_requests", "Number of requests in flight")
        self.REQ_LATENCY = Histogram(
            "request_latency_seconds", "Request latency in seconds"
        )
        self._latency_samples = []  # Each entry: (timestamp, latency)
        self._latency_lock = threading.Lock()
        logger.info("MetricsManager initialized.")

    async def prometheus_middleware(self, request, call_next):
        start = time.time()
        self.IN_FLIGHT.inc()
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.time() - start
            self.IN_FLIGHT.dec()
            self.REQ_LATENCY.observe(elapsed)
            now = time.time()
            with self._latency_lock:
                self._latency_samples.append((now, elapsed))
                # Remove samples older than window
                cutoff = now - Config.LATENCY_WINDOW_SECONDS
                while self._latency_samples and self._latency_samples[0][0] < cutoff:
                    self._latency_samples.pop(0)
            logger.debug(
                f"Request processed in {elapsed:.4f}s. In-flight: {self.get_in_flight()}"
            )

    def get_in_flight(self):
        val = self.IN_FLIGHT._value.get()
        logger.debug(f"Current in-flight requests: {val}")
        return val

    def get_avg_latency(self):
        total = 0.0
        count = 0.0
        for metric in self.REQ_LATENCY.collect():
            for sample in metric.samples:
                if sample.name.endswith("_sum"):
                    total = sample.value
                if sample.name.endswith("_count"):
                    count = sample.value
        avg = (total / count) if count else 0.0
        logger.debug(f"Average latency: {avg:.4f}s")
        return avg

    def get_windowed_avg_latency(self):
        with self._latency_lock:
            if not self._latency_samples:
                logger.debug("No latency samples for windowed average.")
                return 0.0
            avg = sum(lat for _, lat in self._latency_samples) / len(
                self._latency_samples
            )
            logger.debug(f"Windowed average latency: {avg:.4f}s")
            return avg
