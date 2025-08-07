from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

import httpx
import asyncio
import os
from src.round_robin_load_balancer import RoundRobinLoadBalancer
from contextlib import asynccontextmanager

PROBE_INTERVAL = int(os.environ.get("PROXY_PROBE_INTERVAL", "60"))

lb = RoundRobinLoadBalancer()

async def probe_backends():
    while True:
        healthy = set()
        backends = lb.list_backends()
        async with httpx.AsyncClient() as client:
            for backend in backends:
                try:
                    resp = await client.get(f"{backend}/healthz", timeout=5)
                    if resp.status_code == 200 and resp.json().get("status") == "ok":
                        healthy.add(backend)
                except Exception:
                    pass
        # Only keep healthy backends
        lb.registered_backends = healthy
        lb.update_backend_iter()
        await asyncio.sleep(PROBE_INTERVAL)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(probe_backends())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)

@app.post("/register")
async def register_backend(data: dict):
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing 'url' in request body."}, status_code=400)
    lb.register(url)
    return {"message": f"Backend {url} registered.", "backends": lb.list_backends()}

@app.post("/unregister")
async def unregister_backend(data: dict):
    url = data.get("url")
    if not url:
        return JSONResponse({"error": "Missing 'url' in request body."}, status_code=400)
    lb.unregister(url)
    return {"message": f"Backend {url} unregistered.", "backends": lb.list_backends()}

@app.get("/backends")
async def list_backends():
    return {"backends": lb.list_backends()}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    backend_url = lb.get_next_backend()
    if not backend_url:
        return Response(content="No backend servers registered.", status_code=503)
    url = f"{backend_url}/{path}"
    method = request.method
    headers = dict(request.headers)
    body = await request.body()

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.request(
                method,
                url,
                headers=headers,
                content=body,
                params=request.query_params,
                timeout=10.0
            )
        except httpx.RequestError as e:
            return Response(content=f"Upstream error: {e}", status_code=502)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() != "content-encoding"}
    )
