
import os
import httpx
import asyncio
import threading
import time
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
latency_lock = threading.Lock()
backend_latency_samples = []  # Each entry: (timestamp, latency)

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
    with latency_lock:
        backend.in_flight_requests += 1
    try:
        response = await call_next(request)
        return response
    finally:
        elapsed = time.time() - start
        now = time.time()
        with latency_lock:
            backend.in_flight_requests -= 1
            backend_latency_samples.append((now, elapsed))
            # Remove samples older than 5 minutes
            cutoff = now - LATENCY_WINDOW_SECONDS
            while backend_latency_samples and backend_latency_samples[0][0] < cutoff:
                backend_latency_samples.pop(0)
            # Update backend.avg_latency
            if backend_latency_samples:
                backend.avg_latency = sum(lat for _, lat in backend_latency_samples) / len(backend_latency_samples)
            else:
                backend.avg_latency = 0.0

@app.get("/healthz", response_model=ProbeResponse)
def health_probe():
    return ProbeResponse(
        status="ok",
        in_flight_requests=backend.in_flight_requests,
        avg_latency=backend.avg_latency
    )
