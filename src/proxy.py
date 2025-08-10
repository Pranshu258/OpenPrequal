import importlib

from fastapi import FastAPI, Request

from contracts.backend import Backend
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


def load_balancer_factory(registry):
    lb_class_path = getattr(
        Config, "LOAD_BALANCER_CLASS", "src.prequal_load_balancer.PrequalLoadBalancer"
    )
    module_name, class_name = lb_class_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    return getattr(module, class_name)(registry)


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
