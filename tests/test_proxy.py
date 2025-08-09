import pytest
from fastapi.testclient import TestClient

from src.proxy import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_register_backend(client):
    resp = client.post("/register", json={"url": "http://localhost:9001"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Backend http://localhost:9001 registered." in data["message"]
    assert any(b["url"] == "http://localhost:9001" for b in data["backends"])


def test_list_backends(client):
    resp = client.get("/backends")
    assert resp.status_code == 200
    data = resp.json()
    assert "backends" in data
    assert isinstance(data["backends"], list)


def test_proxy_no_backend(client):
    # Unregister all backends
    client.post("/unregister", json={"url": "http://localhost:9001"})
    resp = client.get("/somepath")
    assert resp.status_code == 503
    assert b"No backend servers registered." in resp.content


def test_unregister_backend(client):
    client.post("/register", json={"url": "http://localhost:9002"})
    resp = client.post("/unregister", json={"url": "http://localhost:9002"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Backend http://localhost:9002 unregistered." in data["message"]
    assert all(b["url"] != "http://localhost:9002" for b in data["backends"])
