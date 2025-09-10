import asyncio
import importlib
import logging
from contextlib import asynccontextmanager
from typing import Any, Type

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import ORJSONResponse

from algorithms.prequal_load_balancer import PrequalLoadBalancer
from config.config import Config
from config.logging_config import setup_logging
from contracts.backend import Backend, RegistrationResponse
from core.registry_factory import RegistryFactory
from core.probe_manager import ProbeManager
from core.probe_pool import ProbePool
from core.probe_task_queue import ProbeTaskQueue
from core.proxy_handler import ProxyHandler

setup_logging()
logger = logging.getLogger(__name__)

# Built-in load balancer classes
LB_CLASSES = {
    "default": PrequalLoadBalancer,
    # Add more mappings here if needed
}


def import_from_string(path: str) -> Type[Any]:
    module_name, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def registry_factory():
    """Create registry instance using the new RegistryFactory."""
    return RegistryFactory.create_registry()


def load_balancer_factory(registry):
    key = getattr(Config, "LOAD_BALANCER_CLASS", "default")
    if key in LB_CLASSES:
        logger.info(f"Using built-in load balancer class: {key}")
        if key == "default":
            # PrequalLoadBalancer needs probe_pool and probe_task_queue
            return LB_CLASSES[key](registry, probe_pool, probe_task_queue)
        return LB_CLASSES[key](registry)
    try:
        logger.info(f"Importing load balancer class from string: {key}")
        return import_from_string(key)(registry)
    except Exception as e:
        logger.error(f"Could not import load balancer class '{key}': {e}")
        raise ImportError(f"Could not import load balancer class '{key}': {e}")


# Initialize probe pool and task queue
probe_pool = ProbePool()
probe_task_queue = ProbeTaskQueue()

# Initialize registry first (needed by probe manager)
registry = registry_factory()

# Initialize probe manager with registry for health management
probe_manager = ProbeManager(probe_pool, probe_task_queue, registry=registry)

# Initialize load balancer
lb_instance = load_balancer_factory(registry)
client = httpx.AsyncClient()
proxy_handler = ProxyHandler(client, registry=registry)


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(probe_manager.run())
    yield
    task.cancel()
    await client.aclose()


app = FastAPI(lifespan=lifespan, default_response_class=ORJSONResponse)


@app.post("/register", response_model=RegistrationResponse)
async def register_backend(data: Backend):
    logger.info(f"Registering backend: {data}")
    # Use the pydantic Backend instance directly in the response model.
    await registry.register(data)
    return RegistrationResponse(status="registered", backend=data)


@app.post("/unregister", response_model=RegistrationResponse)
async def unregister_backend(data: Backend):
    logger.info(f"Unregistering backend: {data}")
    await registry.unregister(data)
    return RegistrationResponse(status="unregistered", backend=data)


@app.api_route(
    "/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
)
async def proxy(request: Request, path: str):
    backend_url = await lb_instance.get_next_backend()
    logger.info(f"Routing request for path '{path}' to backend: {backend_url}")
    return await proxy_handler.handle_proxy(request, path, backend_url)
