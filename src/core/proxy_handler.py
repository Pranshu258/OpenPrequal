from typing import Optional

import importlib
import logging

import httpx
from fastapi import Request, Response

from abstractions.registry import Registry
from config.config import Config
from config.logging_config import setup_logging
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)


class ProxyHandler:
    """
    Handler for proxying HTTP requests to backend services, with support for custom hooks.
    """

    @Profiler.profile
    def __init__(
        self, 
        client: httpx.AsyncClient, 
        registry: Optional[Registry] = None,
        consecutive_failure_threshold: int = 3
    ):
        self.client = client
        self.registry = registry
        self.consecutive_failure_threshold = consecutive_failure_threshold
        # Track consecutive failures per backend
        self._consecutive_failures = {}  # backend_url -> failure_count

    @Profiler.profile
    async def handle_proxy(self, request: Request, path: str, backend_url: str):
        """
        Proxy an incoming HTTP request to the specified backend URL, applying custom hooks if configured.

        Args:
            request (Request): The incoming FastAPI request object.
            path (str): The path to append to the backend URL.
            backend_url (str): The URL of the backend service to proxy to.

        Returns:
            Response: The FastAPI response object from the backend or error response.
        """
        if not backend_url:
            logger.error("No backend servers registered. Returning 503.")
            return Response(content="No backend servers registered.", status_code=503)

        # Circuit breaker: Check if backend is known to be unhealthy before making request
        if self.registry:
            is_healthy = await self.registry.is_backend_healthy(backend_url)
            if not is_healthy:
                logger.warning(f"Rejecting request to unhealthy backend {backend_url}")
                return Response(content="Backend temporarily unavailable.", status_code=503)

        rewrite_path = getattr(Config, "CUSTOM_PATH_REWRITE", None)
        if rewrite_path:
            module_name, func_name = rewrite_path.rsplit(".", 1)
            module = importlib.import_module(module_name)
            path = getattr(module, func_name)(path, request)
            logger.debug(f"Path rewritten using custom hook: {path}")

        url = f"{backend_url.rstrip('/')}/{path.lstrip('/')}"
        method = request.method
        headers = dict(request.headers)
        body = await request.body()
        logger.info(f"Proxying {method} request to {url}")

        custom_request_hook = getattr(Config, "CUSTOM_REQUEST_HOOK", None)
        if custom_request_hook:
            module_name, func_name = custom_request_hook.rsplit(".", 1)
            module = importlib.import_module(module_name)
            await getattr(module, func_name)(request, url, headers, body)
            logger.debug("Custom request hook executed.")

        try:
            resp = await self.client.request(
                method,
                url,
                headers=headers,
                content=body,
                params=request.query_params,
                timeout=httpx.Timeout(10.0, read=15.0),
            )
            logger.info(f"Received response from backend: {resp.status_code}")
            
            # Check if response indicates a failure
            if resp.status_code >= 500:
                await self._handle_proxy_failure(backend_url)
            else:
                # Reset consecutive failure count on successful response
                self._consecutive_failures.pop(backend_url, None)
                
        except httpx.TimeoutException as e:
            logger.error("Upstream timeout error", exc_info=e)
            await self._handle_proxy_failure(backend_url)
            return Response(content=f"Upstream timeout: {str(e)}", status_code=504)
        except httpx.RequestError as e:
            logger.error("Upstream request error", exc_info=e)
            await self._handle_proxy_failure(backend_url)
            return Response(content=f"Upstream error: {repr(e)}", status_code=502)

        custom_response_hook = getattr(Config, "CUSTOM_RESPONSE_HOOK", None)
        if custom_response_hook:
            module_name, func_name = custom_response_hook.rsplit(".", 1)
            module = importlib.import_module(module_name)
            await getattr(module, func_name)(resp)
            logger.debug("Custom response hook executed.")

        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers={
                k: v for k, v in resp.headers.items() if k.lower() != "content-encoding"
            },
        )

    async def _handle_proxy_failure(self, backend_url: str):
        """Handle proxy failure by tracking consecutive failures and marking backend unhealthy if threshold is exceeded."""
        self._consecutive_failures[backend_url] = self._consecutive_failures.get(backend_url, 0) + 1
        failure_count = self._consecutive_failures[backend_url]
        
        logger.warning(f"Backend {backend_url} has {failure_count} consecutive proxy failures")
        
        if failure_count >= self.consecutive_failure_threshold and self.registry:
            await self.registry.mark_backend_unhealthy(backend_url)
            logger.warning(f"Backend {backend_url} marked unhealthy after {failure_count} consecutive proxy failures")
