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
        
        # Pre-compute temperature outside the lock to reduce lock time
        temp_rif_values = None
        temp_temperature = None
        
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
            
            # Copy rif_values for median calculation outside lock
            temp_rif_values = list(entry["rif_values"])
            
            entry["timestamp"] = now
            entry["current_latency"] = sum(entry["latencies"]) / len(entry["latencies"])
        
        # Calculate median outside lock to minimize lock time
        if temp_rif_values:
            rif_median = median(temp_rif_values)
            temp_temperature = "hot" if rif_value > rif_median else "cold"
            
            # Quick lock to update temperature
            async with self._lock:
                if backend_id in self.probes:  # Double-check in case it was removed
                    self.probes[backend_id]["temperature"] = temp_temperature

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

    @Profiler.profile
    async def get_backend_data_batch(self, backend_ids):
        """Return a batch of all backend data (temperatures, latencies, rifs) in a single lock acquisition."""
        async with self._lock:
            temperatures = []
            latencies = []
            rifs = []
            for bid in backend_ids:
                probe = self.probes.get(bid, {})
                temperatures.append(probe.get("temperature", None))
                latencies.append(probe.get("current_latency", None))
                rifs.append(probe.get("current_rif", None))
            return temperatures, latencies, rifs