import asyncio
import time
from collections import deque

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
            entry["timestamp"] = now
            entry["current_latency"] = sum(entry["latencies"]) / len(entry["latencies"])

    @Profiler.profile
    async def get_current_latency(self, backend_id):
        # Use a faster check that doesn't require lock for read operations
        if backend_id not in self.probes:
            return None

        async with self._lock:
            if backend_id in self.probes:
                return self.probes[backend_id]["current_latency"]
            return None

    @Profiler.profile
    async def get_rif_values(self, backend_id):
        # Use a faster check that doesn't require lock for read operations
        if backend_id not in self.probes:
            return []

        async with self._lock:
            if backend_id in self.probes:
                # Return a list copy to avoid external modifications
                return list(self.probes[backend_id]["rif_values"])
            return []
