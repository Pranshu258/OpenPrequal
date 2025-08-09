import importlib

import httpx
from fastapi import Request, Response

from src.config import Config


class ProxyHandler:
    def __init__(self, load_balancer):
        self.load_balancer = load_balancer

    async def handle_proxy(self, request: Request, path: str):
        backend_url = self.load_balancer.get_next_backend()
        if not backend_url:
            return Response(content="No backend servers registered.", status_code=503)
        rewrite_path = getattr(Config, "CUSTOM_PATH_REWRITE", None)
        if rewrite_path:
            module_name, func_name = rewrite_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            path = getattr(module, func_name)(path, request)
        url = f"{backend_url}/{path}"
        method = request.method
        headers = dict(request.headers)
        body = await request.body()
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
                    timeout=10.0,
                )
            except httpx.RequestError as e:
                return Response(content=f"Upstream error: {e}", status_code=502)
        custom_response_hook = getattr(Config, "CUSTOM_RESPONSE_HOOK", None)
        if custom_response_hook:
            module_name, func_name = custom_response_hook.rsplit(".", 1)
            module = importlib.import_module(module_name)
            await getattr(module, func_name)(resp)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={
                k: v for k, v in resp.headers.items() if k.lower() != "content-encoding"
            },
        )
