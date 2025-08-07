
import os
import httpx
import asyncio
import random
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.probe_response import ProbeResponse
from src.backend import Backend
from src.config import Config
# Prometheus metrics and helpers
from src.probe_manager import prometheus_middleware, get_in_flight, get_avg_latency

backend = Backend(
    url=Config.BACKEND_URL,
    port=int(Config.BACKEND_PORT),
    health=True,
)

async def send_heartbeat():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.post(f"{Config.PROXY_URL}/register", json={"url": Config.BACKEND_URL})
                if resp.status_code == 200:
                    print(f"[Heartbeat] Registered with proxy at {Config.PROXY_URL} as {Config.BACKEND_URL}")
                else:
                    print(f"[Heartbeat] Failed to register with proxy: {resp.text}")
            except Exception as e:
                print(f"[Heartbeat] Error registering with proxy: {e}")
            await asyncio.sleep(Config.HEARTBEAT_SECONDS)

@asynccontextmanager
async def lifespan(app):
    # Start heartbeat background task
    task = asyncio.create_task(send_heartbeat())
    yield
    task.cancel()

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
        avg_latency=get_avg_latency()
    )
