import os


class Config:
    """
    Configuration class for environment variables and default settings.
    """

    PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
    BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
    BACKEND_HOST = os.environ.get("BACKEND_HOST")
    # Prefer BACKEND_URL if set, else construct from BACKEND_HOST and BACKEND_PORT, else default to localhost
    BACKEND_URL = os.environ.get(
        "BACKEND_URL",
        (
            f"http://{BACKEND_HOST}:{BACKEND_PORT}"
            if BACKEND_HOST
            else f"http://localhost:{BACKEND_PORT}"
        ),
    )
    HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "30"))
    HEARTBEAT_TIMEOUT = int(
        os.environ.get("BACKEND_HEARTBEAT_TIMEOUT", str(2 * HEARTBEAT_SECONDS))
    )
    LATENCY_WINDOW_SECONDS = int(
        os.environ.get("LATENCY_WINDOW_SECONDS", "300")
    )  # 5 minutes

    # Allow health check path to be set for any API service
    BACKEND_HEALTH_PATH = os.environ.get("BACKEND_HEALTH_PATH", "/probe")

    # Optional: allow custom hooks for registration, path rewrite, request/response
    CUSTOM_REGISTER_HOOK = os.environ.get("CUSTOM_REGISTER_HOOK")
    CUSTOM_UNREGISTER_HOOK = os.environ.get("CUSTOM_UNREGISTER_HOOK")
    CUSTOM_PATH_REWRITE = os.environ.get("CUSTOM_PATH_REWRITE")
    CUSTOM_REQUEST_HOOK = os.environ.get("CUSTOM_REQUEST_HOOK")
    CUSTOM_RESPONSE_HOOK = os.environ.get("CUSTOM_RESPONSE_HOOK")

    # Load balancer class selection
    LOAD_BALANCER_CLASS = os.environ.get("LOAD_BALANCER_CLASS", "default")
