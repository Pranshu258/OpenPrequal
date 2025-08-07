
import os
import httpx
import asyncio
import time
from prometheus_client import Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
from fastapi import FastAPI
from contextlib import asynccontextmanager

from src.probe_response import ProbeResponse
from src.backend import Backend

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "30"))

LATENCY_WINDOW_SECONDS = 300  # 5 minutes
backend = Backend(
    url=BACKEND_URL,
    port=int(BACKEND_PORT),
    health=True,
)

# Prometheus metrics
IN_FLIGHT = Gauge('in_flight_requests', 'Number of requests in flight')
REQ_LATENCY = Histogram('request_latency_seconds', 'Request latency in seconds')

async def send_heartbeat():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.post(f"{PROXY_URL}/register", json={"url": BACKEND_URL})
                if resp.status_code == 200:
                    print(f"[Heartbeat] Registered with proxy at {PROXY_URL} as {BACKEND_URL}")
                else:
                    print(f"[Heartbeat] Failed to register with proxy: {resp.text}")
            except Exception as e:
                print(f"[Heartbeat] Error registering with proxy: {e}")
            await asyncio.sleep(HEARTBEAT_SECONDS)

@asynccontextmanager
async def lifespan(app):
    # Start heartbeat background task
    task = asyncio.create_task(send_heartbeat())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": f"Hello from backend at {BACKEND_URL}!"}

@app.middleware("http")
async def track_latency_and_requests(request, call_next):
    start = time.time()
    IN_FLIGHT.inc()
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.time() - start
        IN_FLIGHT.dec()
        REQ_LATENCY.observe(elapsed)

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.get("/healthz", response_model=ProbeResponse)
def health_probe():
    # Get in-flight requests from Prometheus Gauge
    in_flight = IN_FLIGHT._value.get()  # ._value is a prometheus_client internal atomic float
    # Get average latency over last 5 minutes from Prometheus Histogram
    # Prometheus client does not provide windowed average, so we use the total average
    count = REQ_LATENCY._sum.get() if hasattr(REQ_LATENCY, '_sum') else 0.0
    num = REQ_LATENCY._count.get() if hasattr(REQ_LATENCY, '_count') else 0
    avg_latency = (count / num) if num else 0.0
    return ProbeResponse(
        status="ok",
        in_flight_requests=int(in_flight),
        avg_latency=avg_latency
    )
