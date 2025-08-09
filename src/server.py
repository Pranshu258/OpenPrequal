import asyncio
import os
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.backend import Backend
from src.config import Config
from src.heartbeat_client import HeartbeatClient
from src.probe_manager import (
    get_avg_latency,
    get_in_flight,
    get_windowed_avg_latency,
    prometheus_middleware,
)
from src.probe_response import ProbeResponse

backend = Backend(
    url=Config.BACKEND_URL,
    port=int(Config.BACKEND_PORT),
    health=True,
)

heartbeat_client = HeartbeatClient(
    backend_url=Config.BACKEND_URL,
    proxy_url=Config.PROXY_URL,
    heartbeat_interval=Config.HEARTBEAT_SECONDS,
)


@asynccontextmanager
async def lifespan(app):
    await heartbeat_client.start()
    yield
    await heartbeat_client.stop()


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def read_root():
    # Simulate network delay between 50ms and 300ms
    await asyncio.sleep(random.uniform(0.05, 0.3))
    return {"message": f"Hello from backend at {Config.BACKEND_URL}!"}


app.middleware("http")(prometheus_middleware)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz", response_model=ProbeResponse)
def health_probe():
    return ProbeResponse(
        status="ok",
        in_flight_requests=int(get_in_flight()),
        avg_latency=get_avg_latency(),
        windowed_latency=get_windowed_avg_latency(),
    )
