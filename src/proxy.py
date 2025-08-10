import importlib
import logging
from typing import Any, Type

from fastapi import FastAPI, Request

from algorithms.prequal_load_balancer import PrequalLoadBalancer
from config.config import Config
from config.logging_config import setup_logging
from contracts.backend import Backend
from core.backend_registry import BackendRegistry
from core.proxy_handler import ProxyHandler

setup_logging()
logger = logging.getLogger(__name__)

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
    heartbeat_timeout = getattr(Config, "HEARTBEAT_TIMEOUT", None)
    if key in REGISTRY_CLASSES:
        logger.info(f"Using built-in registry class: {key}")
        return REGISTRY_CLASSES[key](heartbeat_timeout=heartbeat_timeout)
    try:
        logger.info(f"Importing registry class from string: {key}")
        return import_from_string(key)(heartbeat_timeout=heartbeat_timeout)
    except Exception as e:
        logger.error(f"Could not import registry class '{key}': {e}")
        raise ImportError(f"Could not import registry class '{key}': {e}")


def load_balancer_factory(registry):
    key = getattr(Config, "LOAD_BALANCER_CLASS", "default")
    if key in LB_CLASSES:
        logger.info(f"Using built-in load balancer class: {key}")
        return LB_CLASSES[key](registry)
    try:
        logger.info(f"Importing load balancer class from string: {key}")
        return import_from_string(key)(registry)
    except Exception as e:
        logger.error(f"Could not import load balancer class '{key}': {e}")
        raise ImportError(f"Could not import load balancer class '{key}': {e}")


registry = registry_factory()
lb_instance = load_balancer_factory(registry)
proxy_handler = ProxyHandler()

app = FastAPI()


@app.post("/register")
async def register_backend(data: Backend):
    logger.info(f"Registering backend: {data}")
    return await registry.register(data)


@app.post("/unregister")
async def unregister_backend(data: Backend):
    logger.info(f"Unregistering backend: {data}")
    return await registry.unregister(data)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def proxy(request: Request, path: str):
    backend_url = lb_instance.get_next_backend()
    logger.info(f"Routing request for path '{path}' to backend: {backend_url}")
    return await proxy_handler.handle_proxy(request, path, backend_url)
