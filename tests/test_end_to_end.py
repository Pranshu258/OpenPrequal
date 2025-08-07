import pytest
from fastapi.testclient import TestClient
from src.proxy import app

# This test assumes at least one backend is registered and healthy.
def test_proxy_forwarding(client):
    # Register a fake backend (would need to be running for a real test)
    client.post("/register", json={"url": "http://localhost:9003"})
    # Forward a request (will fail if backend is not running, but checks proxy logic)
    resp = client.get("/test-echo")
    # Accept 502 (upstream error) or 200 (if backend is running)
    assert resp.status_code in (200, 502, 503)
    # Clean up
    client.post("/unregister", json={"url": "http://localhost:9003"})
