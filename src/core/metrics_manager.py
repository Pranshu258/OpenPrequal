import logging
import time
from bisect import bisect_left
from collections import defaultdict, deque
from statistics import median

from prometheus_client import Gauge, Histogram

from config.logging_config import setup_logging
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)


class MetricsManager:
    """
    Manager for collecting and reporting backend metrics such as in-flight requests and latency.
    """

    @Profiler.profile
    def __init__(self, rif_bins: list[int] | None = None):
        """
        Initialize the MetricsManager and set up Prometheus metrics.

        Args:
            rif_bins: Optional list of increasing integer RIF upper-bounds to bin
                samples by. If provided, latencies are recorded under the bin whose
                upper-bound is the first value >= the observed RIF. If None, the
                exact RIF values are used (previous behavior).
        """
        self.IN_FLIGHT = Gauge("in_flight_requests", "Number of requests in flight")
        self.REQ_LATENCY = Histogram(
            "request_latency_seconds", "Request latency in seconds"
        )
        # Map of RIF (Requests In-Flight) -> deque of recent latencies (max 1000)
        self._rif_latencies = defaultdict(lambda: deque(maxlen=1000))
        # Removed asyncio.Lock for performance; risk of lost sample is acceptable for metrics
        # maintain set of RIF keys with recorded samples (sort only when needed)
        self._active_rif_keys = set()
        # Optional bin configuration (sorted, unique)
        if rif_bins is not None and len(rif_bins) > 0:
            self._rif_bins = sorted(set(rif_bins))
        else:
            self._rif_bins = None
        logger.info("MetricsManager initialized.")

    # Helper: map an observed RIF to a storage key (either exact RIF or bin upper-bound)
    @Profiler.profile
    def _get_rif_key(self, rif: int) -> int:
        if not self._rif_bins:
            return rif
        # Choose the first bin upper-bound that is >= rif; if larger than any bin,
        # clamp to the largest bin.
        idx = bisect_left(self._rif_bins, rif)
        if idx >= len(self._rif_bins):
            return self._rif_bins[-1]
        return self._rif_bins[idx]

    @Profiler.profile
    async def prometheus_middleware(self, request, call_next):
        """
        Middleware for tracking request metrics and updating Prometheus gauges/histograms.

        Args:
            request: The incoming request object.
            call_next: The next handler in the middleware chain.

        Returns:
            The response object from the next handler.
        """
        start = time.time()
        self.IN_FLIGHT.inc()
        rif_at_start = int(self.get_in_flight())
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed = time.time() - start
            self.IN_FLIGHT.dec()
            self.REQ_LATENCY.observe(elapsed)
            # Store latency under the RIF observed at request start (no lock for speed)
            key = self._get_rif_key(rif_at_start)
            self._rif_latencies[key].append(elapsed)
            self._active_rif_keys.add(key)
            logger.debug(
                f"Request processed in {elapsed:.4f}s. In-flight: {self.get_in_flight()}"
            )

    @Profiler.profile
    def get_in_flight(self):
        """
        Get the current number of in-flight requests.

        Returns:
            float: Number of in-flight requests.
        """
        val = self.IN_FLIGHT._value.get()
        logger.debug(f"Current in-flight requests: {val}")
        return val

    @Profiler.profile
    async def get_avg_latency(self):
        """
        Get the median request latency for the current RIF (requests in-flight) value.

        Returns:
            float: Median latency in seconds for the current RIF, or 0.0 if none.
        """
        current_rif = int(self.get_in_flight())
        key = self._get_rif_key(current_rif)
        samples = list(self._rif_latencies.get(key, ()))
        if samples:
            med = float(median(samples))
            logger.debug(
                f"Median latency for RIF={current_rif} (key={key}): {med:.4f}s (exact)"
            )
            return med

        # use tracked active RIF keys with samples
        rif_keys = [
            k
            for k in sorted(self._active_rif_keys)
            if len(self._rif_latencies.get(k, [])) > 0
        ]
        if not rif_keys:
            logger.debug("No latency samples recorded yet; returning 0.0")
            return 0.0

        idx = bisect_left(rif_keys, key)
        lower_key = rif_keys[idx - 1] if idx > 0 else None
        higher_key = rif_keys[idx] if idx < len(rif_keys) else None

        if lower_key is not None and higher_key is None:
            med_lower = float(median(self._rif_latencies[lower_key]))
            logger.debug(
                f"No exact samples for RIF={current_rif}; using lower RIF={lower_key} median {med_lower:.4f}s"
            )
            return med_lower

        if higher_key is not None and lower_key is None:
            med_higher = float(median(self._rif_latencies[higher_key]))
            logger.debug(
                f"No exact samples for RIF={current_rif}; using higher RIF={higher_key} median {med_higher:.4f}s"
            )
            return med_higher

        if lower_key is not None and higher_key is not None:
            med_lower = float(median(self._rif_latencies[lower_key]))
            med_higher = float(median(self._rif_latencies[higher_key]))
            if higher_key == lower_key:
                logger.debug(
                    f"Degenerate neighbor case for RIF={current_rif}; returning median {med_lower:.4f}s"
                )
                return med_lower
            t = (key - lower_key) / (higher_key - lower_key)
            estimate = med_lower + t * (med_higher - med_lower)
            logger.debug(
                (
                    f"Estimated median latency for RIF={current_rif} (key={key}) by interpolating "
                    f"lower RIF={lower_key} ({med_lower:.4f}s) and higher RIF={higher_key} ({med_higher:.4f}s): "
                    f"{estimate:.4f}s"
                )
            )
            return float(estimate)
        return 0.0
