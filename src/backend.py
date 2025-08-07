


import os
import httpx
import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "120"))

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
