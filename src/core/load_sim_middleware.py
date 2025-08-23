import asyncio
import random

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.metrics_manager import MetricsManager

RIF_THRESHOLD = 500
LATENCY_PER_RIF = 0.001  # 1ms per RIF, adjust as needed


class LoadSimMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics_manager: MetricsManager):
        super().__init__(app)
        self.metrics_manager = metrics_manager
        self.jitter_mul = random.uniform(0, 3)

    async def dispatch(self, request: Request, call_next):
        rif_count = int(self.metrics_manager.get_in_flight())
        # if rif_count > RIF_THRESHOLD:
        #     return JSONResponse(
        #         status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        #         content={"detail": "Service Unavailable: too many concurrnt requests!"},
        #     )
        # Simulate latency: fixed mean/stddev, plus jitter based on RIF
        mean = 0.05  # 50ms
        stddev = 0.01  # 10ms
        base_latency = max(0, random.gauss(mean, stddev))
        jitter = random.uniform(0, rif_count * 0.001)  # up to 1ms per RIF as jitter
        latency = self.jitter_mul * (base_latency + jitter)
        await asyncio.sleep(latency)
        response = await call_next(request)
        return response
