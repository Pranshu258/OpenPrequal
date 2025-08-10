import importlib
from typing import Any, Type

from fastapi import FastAPI, Request

from algorithms.prequal_load_balancer import PrequalLoadBalancer
from config.config import Config
from contracts.backend import Backend
from core.backend_registry import BackendRegistry
from core.proxy_handler import ProxyHandler

# Built-in registry and load balancer classes
REGISTRY_CLASSES = {
    "default": BackendRegistry,
    # Add more mappings here if needed
}
LB_CLASSES = {
    "default": PrequalLoadBalancer,
    # Add more mappings here if needed
}


def import_from_string(path: str) -> Type[Any]:
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def registry_factory():
    key = getattr(Config, "REGISTRY_CLASS", "default")
    if key in REGISTRY_CLASSES:
        return REGISTRY_CLASSES[key]()
    try:
        return import_from_string(key)()
    except Exception as e:
        raise ImportError(f"Could not import registry class '{key}': {e}")


def load_balancer_factory(registry):
    key = getattr(Config, "LOAD_BALANCER_CLASS", "default")
    if key in LB_CLASSES:
        return LB_CLASSES[key](registry)
    try:
        return import_from_string(key)(registry)
    except Exception as e:
        raise ImportError(f"Could not import load balancer class '{key}': {e}")


registry = registry_factory()
lb_instance = load_balancer_factory(registry)
proxy_handler = ProxyHandler()

app = FastAPI()


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
    backend_url = lb_instance.get_next_backend()
    return await proxy_handler.handle_proxy(request, path, backend_url)
