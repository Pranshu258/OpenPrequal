import asyncio
import time
from collections import deque
from statistics import median

from core.profiler import Profiler


class ProbePool:
    @Profiler.profile
    def __init__(self):
        # Structure: {backend_id: {'latencies': deque, 'rif_values': deque, 'timestamp': float, 'current_latency': float}}
        self.probes = {}
        self.max_backends = 16
        self._lock = asyncio.Lock()

    @Profiler.profile
    async def add_probe(self, backend_id, latency, rif_value):
        now = time.time()
        async with self._lock:
            if backend_id not in self.probes:
                if len(self.probes) >= self.max_backends:
                    # Remove the oldest backend (FIFO)
                    oldest_backend = next(iter(self.probes))
                    del self.probes[oldest_backend]
                self.probes[backend_id] = {
                    "latencies": deque(maxlen=1000),
                    "rif_values": deque(maxlen=1000),
                    "timestamp": now,
                    "current_rif": 0.0,
                    "current_latency": 0.0,
                }
            entry = self.probes[backend_id]
            entry["latencies"].append(latency)
            entry["rif_values"].append(rif_value)
            entry["temperature"] = "hot" if rif_value > median(entry["rif_values"]) else "cold"
            entry["timestamp"] = now
            entry["current_latency"] = sum(entry["latencies"]) / len(entry["latencies"])

    @Profiler.profile
    async def get_current_rifs(self, backend_ids):
        """Return a list of current RIFs for the given backend_ids, in order."""
        # Use a single lock for all reads
        async with self._lock:
            return [self.probes.get(bid, {}).get("current_rif", None) for bid in backend_ids]

    @Profiler.profile
    async def get_current_latencies(self, backend_ids):
        """Return a list of current latencies for the given backend_ids, in order."""
        async with self._lock:
            return [self.probes.get(bid, {}).get("current_latency", None) for bid in backend_ids]

    @Profiler.profile
    async def get_current_temperatures(self, backend_ids):
        """Return a list of current temperatures for the given backend_ids, in order."""
        async with self._lock:
            return [self.probes.get(bid, {}).get("temperature", None) for bid in backend_ids]