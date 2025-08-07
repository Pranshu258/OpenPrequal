

import os
import httpx
from fastapi import FastAPI
from contextlib import asynccontextmanager

PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
BACKEND_URL = f"http://localhost:{BACKEND_PORT}"

@asynccontextmanager
async def lifespan(app):
    # Register with proxy on startup
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(f"{PROXY_URL}/register", json={"url": BACKEND_URL})
            if resp.status_code == 200:
                print(f"Registered with proxy at {PROXY_URL} as {BACKEND_URL}")
            else:
                print(f"Failed to register with proxy: {resp.text}")
        except Exception as e:
            print(f"Error registering with proxy: {e}")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def read_root():
    return {"message": f"Hello from backend at {BACKEND_URL}!"}
