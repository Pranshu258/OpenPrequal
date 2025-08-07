from typing import Optional

class Backend:
    def __init__(self, url: str, port: Optional[int] = None, health: bool = False):
        self.url = url
        self.port = port
        self.health = health

    def __eq__(self, other):
        if not isinstance(other, Backend):
            return False
        return self.url == other.url and self.port == other.port

    def __hash__(self):
        return hash((self.url, self.port))

    def __repr__(self):
        return f"Backend(url={self.url}, port={self.port}, health={self.health})"



import os
import httpx
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "60"))

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

@app.get("/healthz")
def health_probe():
    return {"status": "ok"}
