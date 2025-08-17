import asyncio

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.metrics_manager import MetricsManager

RIF_THRESHOLD = 300
LATENCY_PER_RIF = 0.001  # 1ms per RIF, adjust as needed


class LoadSimMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics_manager: MetricsManager):
        super().__init__(app)
        self.metrics_manager = metrics_manager

    async def dispatch(self, request: Request, call_next):
        rif_count = int(self.metrics_manager.get_in_flight())
        if rif_count > RIF_THRESHOLD:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service Unavailable: too many concurrnt requests!"},
            )
        # Simulate latency proportional to RIF
        await asyncio.sleep(rif_count * LATENCY_PER_RIF)
        response = await call_next(request)
        return response
