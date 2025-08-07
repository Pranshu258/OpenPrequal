import os

class Config:
    PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
    BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
    BACKEND_URL = os.environ.get("BACKEND_URL", f"http://localhost:{BACKEND_PORT}")
    HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "30"))
    LATENCY_WINDOW_SECONDS = int(os.environ.get("LATENCY_WINDOW_SECONDS", "300"))  # 5 minutes

    # Reusability: allow load balancer class to be set via env/config
    LOAD_BALANCER_CLASS = os.environ.get("LOAD_BALANCER_CLASS", "src.prequal_load_balancer.PrequalLoadBalancer")
    # Allow health check path to be set for any API service
    BACKEND_HEALTH_PATH = os.environ.get("BACKEND_HEALTH_PATH", "/healthz")

    # Optional: allow custom hooks for registration, path rewrite, request/response
    CUSTOM_REGISTER_HOOK = os.environ.get("CUSTOM_REGISTER_HOOK")
    CUSTOM_UNREGISTER_HOOK = os.environ.get("CUSTOM_UNREGISTER_HOOK")
    CUSTOM_PATH_REWRITE = os.environ.get("CUSTOM_PATH_REWRITE")
    CUSTOM_REQUEST_HOOK = os.environ.get("CUSTOM_REQUEST_HOOK")
    CUSTOM_RESPONSE_HOOK = os.environ.get("CUSTOM_RESPONSE_HOOK")
