import asyncio
import importlib
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, Response

from src.backend import Backend
from src.backend_probe_manager import BackendProbeManager
from src.backend_registry import BackendRegistry
from src.config import Config
from src.proxy_handler import ProxyHandler


# Create registry first, then pass it to the load balancer
def registry_factory():
    registry_path = getattr(
        Config, "REGISTRY_CLASS", "src.backend_registry.BackendRegistry"
    )
    module_name, class_name = registry_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


registry = registry_factory()


def load_balancer_factory(registry):
    lb_class_path = getattr(
        Config, "LOAD_BALANCER_CLASS", "src.prequal_load_balancer.PrequalLoadBalancer"
    )
    module_name, class_name = lb_class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(registry)


lb_instance = load_balancer_factory(registry)
probe_manager = BackendProbeManager(lb_instance)
proxy_handler = ProxyHandler(lb_instance)


@asynccontextmanager
async def lifespan(app):
    await probe_manager.start()
    yield
    await probe_manager.stop()


app = FastAPI(lifespan=lifespan)


@app.post("/register")
async def register_backend(data: Backend):
    return await registry.register(data)


@app.post("/unregister")
async def unregister_backend(data: Backend):
    return await registry.unregister(data)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def proxy(request: Request, path: str):
    return await proxy_handler.handle_proxy(request, path)
