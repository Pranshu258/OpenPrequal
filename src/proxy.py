from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

import httpx
import asyncio

from src.config import Config


# Allow pluggable load balancer class via config or env
import importlib
from src.probe_response import ProbeResponse
from contextlib import asynccontextmanager

def get_load_balancer():
    lb_class_path = getattr(Config, "LOAD_BALANCER_CLASS", "src.prequal_load_balancer.PrequalLoadBalancer")
    module_name, class_name = lb_class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()

PROBE_INTERVAL = int(getattr(Config, "PROXY_PROBE_INTERVAL", 60))

lb = get_load_balancer()

async def probe_backends():
    # Health check logic can be customized per service type
    while True:
        async with httpx.AsyncClient() as client:
            for backend in list(lb.registered_backends):
                try:
                    # Allow health endpoint to be customized
                    health_path = getattr(Config, "BACKEND_HEALTH_PATH", "/healthz")
                    resp = await client.get(f"{backend.url}{health_path}", timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        probe = ProbeResponse(**data)
                        backend.health = probe.status == "ok"
                        backend.in_flight_requests = getattr(probe, "in_flight_requests", 0)
                        backend.avg_latency = getattr(probe, "avg_latency", 0.0)
                        backend.windowed_latency = getattr(probe, "windowed_latency", 0.0)
                    else:
                        backend.health = False
                except Exception:
                    backend.health = False
        await asyncio.sleep(PROBE_INTERVAL)

@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(probe_backends())
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)


# Registration endpoint is generic, can be extended for auth, metadata, etc.
@app.post("/register")
async def register_backend(data: dict):
    url = data.get("url")
    port = data.get("port")
    # Allow for custom registration logic via hook
    custom_register = getattr(Config, "CUSTOM_REGISTER_HOOK", None)
    if custom_register:
        module_name, func_name = custom_register.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return await getattr(module, func_name)(data, lb)
    if not url:
        return JSONResponse({"error": "Missing 'url' in request body."}, status_code=400)
    lb.register(url, port)
    return {"message": f"Backend {url} registered.", "backends": lb.list_backends()}


@app.post("/unregister")
async def unregister_backend(data: dict):
    url = data.get("url")
    port = data.get("port")
    # Allow for custom unregister logic via hook
    custom_unregister = getattr(Config, "CUSTOM_UNREGISTER_HOOK", None)
    if custom_unregister:
        module_name, func_name = custom_unregister.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return await getattr(module, func_name)(data, lb)
    if not url:
        return JSONResponse({"error": "Missing 'url' in request body."}, status_code=400)
    lb.unregister(url, port)
    return {"message": f"Backend {url} unregistered.", "backends": lb.list_backends()}

@app.get("/backends")
async def list_backends():
    return {"backends": lb.list_backends()}


# Generic proxy endpoint, supports all HTTP methods and paths
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def proxy(request: Request, path: str):
    backend_url = lb.get_next_backend()
    if not backend_url:
        return Response(content="No backend servers registered.", status_code=503)
    # Allow for custom path rewriting or header injection
    rewrite_path = getattr(Config, "CUSTOM_PATH_REWRITE", None)
    if rewrite_path:
        module_name, func_name = rewrite_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        path = getattr(module, func_name)(path, request)
    url = f"{backend_url}/{path}"
    method = request.method
    headers = dict(request.headers)
    body = await request.body()

    # Allow for custom request/response hooks
    custom_request_hook = getattr(Config, "CUSTOM_REQUEST_HOOK", None)
    if custom_request_hook:
        module_name, func_name = custom_request_hook.rsplit(".", 1)
        module = importlib.import_module(module_name)
        await getattr(module, func_name)(request, url, headers, body)

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

    # Allow for custom response hook
    custom_response_hook = getattr(Config, "CUSTOM_RESPONSE_HOOK", None)
    if custom_response_hook:
        module_name, func_name = custom_response_hook.rsplit(".", 1)
        module = importlib.import_module(module_name)
        await getattr(module, func_name)(resp)

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers={k: v for k, v in resp.headers.items() if k.lower() != "content-encoding"}
    )
