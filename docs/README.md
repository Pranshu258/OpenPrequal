# OpenPrequal API Gateway & Load Balancer

OpenPrequal is a reusable, configurable API gateway and load balancer for any HTTP-based backend service. It supports dynamic backend registration, health checks, pluggable load balancing strategies, and proxying of all HTTP methods.

Based on Google's Prequal Load Balancing Algorithm - [Load is not what you should balance](https://research.google/pubs/load-is-not-what-you-should-balance-introducing-prequal/)


## Architecture Diagram
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

_Backends register/unregister with the proxy. Proxy performs health checks and load balances requests._

## Features
- **Dynamic Backend Registration**: Backends can register/unregister themselves at runtime.
- **Health Checks**: Periodic health checks to ensure only healthy backends receive traffic.
- **Pluggable Load Balancer**: Easily switch between load balancing strategies (round robin, least latency, etc.) via config.
- **Generic Proxy**: Proxies any HTTP method and path to registered backends.
- **Customizable Hooks**: Support for custom registration, path rewriting, request/response hooks, and more.
- **Prometheus Metrics**: Built-in metrics for monitoring.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```


### 2. Start the Proxy
```bash
PYTHONPATH=src uvicorn proxy:app --port 8000
```

### 3. Start a Backend Example
```bash
PROXY_URL=http://localhost:8000 BACKEND_PORT=8001 PYTHONPATH=src uvicorn server:app --port 8001
```

### 4. Register a Backend (if not using heartbeat)
```bash
curl -X POST http://localhost:8000/register -H 'Content-Type: application/json' -d '{"url": "http://localhost:8001"}'
```

### 5. Proxy Requests
```bash
curl http://localhost:8000/
```

## Configuration

All configuration can be set via environment variables or by editing `src/config/config.py`:
- `LOAD_BALANCER_CLASS`: Python path to the load balancer class (default: `algorithms.prequal_load_balancer.PrequalLoadBalancer`)
- `REGISTRY_CLASS`: Python path to the registry class (default: `core.backend_registry.BackendRegistry`)
- `BACKEND_HEALTH_PATH`: Path for health checks (default: `/healthz`)
- `CUSTOM_REGISTER_HOOK`, `CUSTOM_UNREGISTER_HOOK`, `CUSTOM_PATH_REWRITE`, `CUSTOM_REQUEST_HOOK`, `CUSTOM_RESPONSE_HOOK`: Python paths to custom hook functions

## Testing
Run all tests with:
```bash
pytest tests/
```

## Extending
- Implement your own load balancer by subclassing `LoadBalancer` in `src/abstractions/load_balancer.py`.
- Add custom hooks for registration, path rewriting, or request/response processing.

## Folder Structure
- `src/` - Source code for proxy, server, load balancers, config, and abstractions
- `tests/` - Automated tests
- `docs/` - Documentation
- `scripts/` - Helper scripts to start/stop servers

# Running OpenPrequal from Source

To run the backend or proxy server from source, use the following best practices for Python projects with a `src/` layout:

## 1. Add `src/` to your `PYTHONPATH`

This ensures all imports like `from config.config import Config` work as expected.

**Example:**

```sh
PYTHONPATH=src uvicorn server:app

```sh
PYTHONPATH=src uvicorn server:app
```

Or, for the proxy:
```sh
PYTHONPATH=src uvicorn proxy:app
```
## 2. Why?

This is the recommended approach for open source Python projects using a `src/` layout. It avoids import errors and makes your codebase more maintainable.

## 3. For Contributors

- Always run scripts and tests with `PYTHONPATH=src`.
- If using an IDE, set the working directory or source roots accordingly.
- All internal imports should be absolute (e.g., `from core.proxy_handler import ProxyHandler`).

---

For more details, see the [Python Packaging Authority's guidance](https://packaging.python.org/en/latest/tutorials/packaging-projects/#structuring-your-project).

## License
MIT License
