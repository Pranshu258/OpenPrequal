import importlib

from fastapi import Depends, Request, Response
from fastapi.responses import JSONResponse

from src.config import Config


class BackendRegistry:
    def __init__(self, load_balancer):
        self.load_balancer = load_balancer

    async def register_backend(self, data: dict):
        url = data.get("url")
        port = data.get("port")
        custom_register = getattr(Config, "CUSTOM_REGISTER_HOOK", None)
        if custom_register:
            module_name, func_name = custom_register.rsplit(".", 1)
            module = importlib.import_module(module_name)
            return await getattr(module, func_name)(data, self.load_balancer)
        if not url:
            return JSONResponse(
                {"error": "Missing 'url' in request body."}, status_code=400
            )
        self.load_balancer.register(url, port)
        return {
            "message": f"Backend {url} registered.",
            "backends": self.load_balancer.list_backends(),
        }

    async def unregister_backend(self, data: dict):
        url = data.get("url")
        port = data.get("port")
        custom_unregister = getattr(Config, "CUSTOM_UNREGISTER_HOOK", None)
        if custom_unregister:
            module_name, func_name = custom_unregister.rsplit(".", 1)
            module = importlib.import_module(module_name)
            return await getattr(module, func_name)(data, self.load_balancer)
        if not url:
            return JSONResponse(
                {"error": "Missing 'url' in request body."}, status_code=400
            )
        self.load_balancer.unregister(url, port)
        return {
            "message": f"Backend {url} unregistered.",
            "backends": self.load_balancer.list_backends(),
        }

    def list_backends(self):
        return {"backends": self.load_balancer.list_backends()}
