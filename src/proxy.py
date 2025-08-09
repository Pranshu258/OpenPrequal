import asyncio
import importlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response

from src.backend_probe_manager import BackendProbeManager
from src.backend_registry import BackendRegistry
from src.config import Config
from src.proxy_handler import ProxyHandler


def load_balancer_factory():
    lb_class_path = getattr(
        Config, "LOAD_BALANCER_CLASS", "src.prequal_load_balancer.PrequalLoadBalancer"
    )
    module_name, class_name = lb_class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


lb_instance = load_balancer_factory()
probe_manager = BackendProbeManager(lb_instance)
registry = BackendRegistry(lb_instance)
proxy_handler = ProxyHandler(lb_instance)


@asynccontextmanager
async def lifespan(app):
    await probe_manager.start()
    yield
    await probe_manager.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/register")
async def register_backend(data: dict):
    return await registry.register_backend(data)


@app.post("/unregister")
async def unregister_backend(data: dict):
    return await registry.unregister_backend(data)


@app.get("/backends")
async def list_backends():
    return registry.list_backends()


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def proxy(request: Request, path: str):
    return await proxy_handler.handle_proxy(request, path)
