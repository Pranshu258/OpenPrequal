# OpenPrequal: API Gateway & Load Balancer

OpenPrequal is a reusable, production-ready API gateway and load balancer for any HTTP-based backend service. It features dynamic backend registration (via heartbeat or manual), health checks, pluggable load balancing strategies (including Google's Prequal algorithm), Prometheus metrics, and full support for Docker and Kubernetes deployments.

---

## Architecture

```
                ┌──────────────┐
                │   Client     │
                └──────┬───────┘
                       │ HTTP Request
                ┌──────▼───────┐
                │   Proxy      │
                │ (API Gateway │
                │  & LB)       │
                └──────-┬──────┘
         ┌──────────────┼──────────────┐
         │              │              │
 ┌───────▼──────┐ ┌─────▼──────┐ ┌────-▼──────┐
 │  Backend 1   │ │ Backend 2  │ │ Backend N  │
 └──────────────┘ └────────────┘ └────────────┘
```

Backends register automatically with the proxy via periodic heartbeats, or can be registered manually. The proxy tracks backend health using heartbeat timeouts and a health check endpoint, and load balances requests to healthy backends.

---

## Features

- **Dynamic Backend Registration:** Backends register/unregister automatically via heartbeat, or can be registered manually.
- **Health Checks:** Proxy tracks backend health using heartbeat timeouts and `/healthz` endpoint.
- **Pluggable Load Balancer:** Switch between Prequal (default), round robin, or custom strategies via config/env.
- **Generic Proxy:** Proxies any HTTP method and path to registered backends.
- **Customizable Hooks:** Support for custom registration, path rewriting, request/response hooks via config/env.
- **Prometheus Metrics:** Built-in `/metrics` endpoint for monitoring (proxy and backend).
- **Docker & Kubernetes Ready:** Includes Dockerfiles, scripts, and Helm chart for easy deployment.
- **Extensive Automated Tests:** All core modules and algorithms are covered by unit tests.

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Proxy
```bash
PYTHONPATH=src uvicorn proxy:app --port 8000
```

### 3. Start a Backend Example (auto-registers via heartbeat)
```bash
PROXY_URL=http://localhost:8000 BACKEND_PORT=8001 PYTHONPATH=src uvicorn server:app --port 8001
```

### 4. (Optional) Register a Backend Manually
If not using heartbeat, you can register a backend manually:
```bash
curl -X POST http://localhost:8000/register -H 'Content-Type: application/json' -d '{"url": "http://localhost:8001", "port": 8001}'
```

### 5. Proxy Requests
```bash
curl http://localhost:8000/
```

### 6. View Metrics
Prometheus metrics are available at:
```bash
curl http://localhost:8000/metrics   # Proxy metrics
curl http://localhost:8001/metrics   # Backend metrics
```

---

## Configuration

All configuration can be set via environment variables or by editing `src/config/config.py`:

- `PROXY_URL`: Proxy URL for backend registration (default: `http://localhost:8000`)
- `BACKEND_PORT`: Port for backend server (default: `8001`)
- `BACKEND_URL`: Backend URL (default: `http://localhost:<BACKEND_PORT>`)
- `BACKEND_HEARTBEAT_SECONDS`: Heartbeat interval in seconds (default: `30`)
- `BACKEND_HEARTBEAT_TIMEOUT`: Heartbeat timeout in seconds (default: `2 * HEARTBEAT_SECONDS`)
- `LATENCY_WINDOW_SECONDS`: Window for average latency metrics (default: `300`)
- `BACKEND_HEALTH_PATH`: Path for health checks (default: `/healthz`)
- `LOAD_BALANCER_CLASS`: Python path to the load balancer class (default: `algorithms.prequal_load_balancer.PrequalLoadBalancer`)
- `REGISTRY_CLASS`: Python path to the registry class (default: `core.backend_registry.BackendRegistry`)
- `CUSTOM_REGISTER_HOOK`, `CUSTOM_UNREGISTER_HOOK`, `CUSTOM_PATH_REWRITE`, `CUSTOM_REQUEST_HOOK`, `CUSTOM_RESPONSE_HOOK`: Python paths to custom hook functions (optional)

---

## Folder Structure

- `src/` - Source code for proxy, server, load balancers, config, and abstractions
    - `abstractions/` - Abstract base classes for load balancer and registry
    - `algorithms/` - Prequal and round robin load balancer implementations
    - `config/` - Configuration and logging setup
    - `contracts/` - Pydantic models for backend and probe response
    - `core/` - Backend registry, heartbeat client, metrics manager, proxy handler
    - `proxy.py` - FastAPI proxy app (API gateway)
    - `server.py` - FastAPI backend app (example backend)
- `tests/` - Automated unit tests for all modules
- `scripts/` - Helper scripts to start/stop servers, run tests, build/push Docker images
- `k8s/` - Kubernetes Helm chart and manifests (deployments, services, Dockerfiles)
- `docs/` - Documentation

---

## Running from Source

### 1. Add `src/` to your `PYTHONPATH`
This ensures all imports like `from config.config import Config` work as expected.

**Example:**
```sh
PYTHONPATH=src uvicorn server:app --port 8001
PYTHONPATH=src uvicorn proxy:app --port 8000
```

Or use the provided scripts in `scripts/` for multi-backend startup:
```sh
bash scripts/start_backends.sh 3   # Starts proxy and 3 backends
```

### 2. Why?
This is the recommended approach for open source Python projects using a `src/` layout. It avoids import errors and makes your codebase more maintainable.

### 3. For Contributors
- Always run scripts and tests with `PYTHONPATH=src`.
- If using an IDE, set the working directory or source roots accordingly.
- All internal imports should be absolute (e.g., `from core.proxy_handler import ProxyHandler`).

---

## Docker & Kubernetes

OpenPrequal includes Dockerfiles for both proxy and backend, and a Helm chart for Kubernetes deployment. See `k8s/` for details.

### Build and run with Docker
```sh
docker build -f k8s/openprequal/docker/Dockerfile.proxy -t openprequal-proxy .
docker build -f k8s/openprequal/docker/Dockerfile.backend -t openprequal-backend .
docker run -d --name openprequal-proxy -p 8000:8000 openprequal-proxy
docker run -d --name openprequal-backend1 -e PROXY_URL=http://host.docker.internal:8000 -e BACKEND_PORT=8001 -p 8001:8001 openprequal-backend
```

### Kubernetes
```sh
cd k8s/openprequal
helm install openprequal .
```

---

## Testing

Run all tests with:
```bash
PYTHONPATH=src pytest tests/
```

---

## Extending

- Implement your own load balancer by subclassing `LoadBalancer` in `src/abstractions/load_balancer.py`.
- Add custom hooks for registration, path rewriting, or request/response processing (see config section).

---

## License

MIT License
