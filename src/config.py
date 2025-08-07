import os

class Config:
    PROXY_URL = os.environ.get("PROXY_URL", "http://localhost:8000")
    BACKEND_PORT = os.environ.get("BACKEND_PORT", "8001")
    BACKEND_URL = f"http://localhost:{BACKEND_PORT}"
    HEARTBEAT_SECONDS = int(os.environ.get("BACKEND_HEARTBEAT_SECONDS", "30"))
    LATENCY_WINDOW_SECONDS = 300  # 5 minutes
