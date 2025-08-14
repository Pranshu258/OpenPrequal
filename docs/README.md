![OpenPrequal Brand](../assets/brand.png)

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Workflow](#workflow)
- [Probe Pool & Probing Architecture](#probe-pool--probing-architecture)
- [Configuration](#configuration)
- [Usage](#usage)
  - [Install Dependencies](#install-dependencies)
  - [Start the Proxy](#start-the-proxy)
  - [Start a Backend Example](#start-a-backend-example)
  - [Manual Backend Registration](#manual-backend-registration)
  - [Proxy Requests](#proxy-requests)
  - [View Metrics](#view-metrics)
- [Running from Source](#running-from-source)
- [Docker & Kubernetes Deployment](#docker--kubernetes-deployment)
- [Testing](#testing)
- [Extending](#extending)
- [License](#license)

## OpenPrequal: API Gateway & Load Balancer
OpenPrequal is a reusable, production-ready API gateway and load balancer for any HTTP-based backend service. It is designed to simplify scaling, reliability, and observability for microservices and distributed systems. OpenPrequal is ideal for:

- Load balancing traffic across multiple backend replicas
- Automatically detecting and routing around unhealthy backends
- Collecting real-time metrics for monitoring and autoscaling
- Supporting dynamic environments (Kubernetes, Docker, bare metal)

It features dynamic backend registration, health checks, pluggable load balancing strategies, Prometheus metrics, and full support for Docker and Kubernetes deployments.

## Features
- **Dynamic Backend Registration:** Backends can register/unregister automatically via heartbeat or manually via API, allowing seamless scaling and failover.
- **Health Checks:** The proxy tracks backend health using heartbeat timeouts and `/probe` endpoint, ensuring requests are only sent to healthy replicas.
- **Pluggable Load Balancer:** Easily switch between Prequal (default), round robin, or custom strategies via config/env. Prequal uses real-time RIF (requests-in-flight) and latency for optimal routing.
- **Generic Proxy:** Proxies any HTTP method and path to registered backends, supporting REST, GraphQL, and custom APIs.
- **Customizable Hooks:** Add custom registration logic, path rewriting, or request/response processing via Python hooks for advanced use cases.
- **Prometheus Metrics:** Built-in `/metrics` endpoint exposes detailed stats for both proxy and backend, ready for Prometheus/Grafana integration.
- **Docker & Kubernetes Ready:** Includes Dockerfiles, scripts, and Helm chart for easy deployment and scaling in cloud-native environments.
- **Extensive Automated Tests:** All core modules and algorithms are covered by unit tests for reliability and maintainability.

## Architecture
OpenPrequal consists of several main components:

- **Proxy (API Gateway):** Receives client requests, selects the best backend, and forwards requests. Exposes `/proxy` and `/metrics` endpoints.
- **Replica Selector:** Uses probe pool data (RIF and latency) to choose the optimal backend for each request.
- **Probe Manager:** Periodically probes all backends to collect health and performance data.
- **Metrics Endpoint:** Exposes Prometheus-compatible metrics for monitoring.
- **Backends:** Each backend implements `/handle` for business logic, `/probe` for health/metrics, and RIF middleware for tracking requests-in-flight.

The diagram below illustrates the flow of requests and probes:
```text
                  ┌────────────────────────────────────────────┐
                  │                  CLIENT                    │
                  └──────────────────────┬─────────────────────┘
                                         |
                                         │  HTTP Request (/proxy)
                                         |
                                         ▼
                      ┌────────────────────────────────────┐
                      │   OPENPREQUAL PROXY (Origin Pod)   │
                      │────────────────────────────────────│
                      │ 1. Replica Selector                │
                      │    - Reads RIF & latency from      │
                      │      probe pool data.              │
                      │                                    │
                      │ 2. Proxy Handler                   │
                      │    - Forwards to best replica      │
                      │                                    │
                      │ 3. Probe Manager                   │
                      │    - Periodically calls probe      │
                      │      on all replicas               │
                      │                                    │
                      │ 4. Metrics Endpoint (/metrics)     │
                      │    - Prometheus stats              │
                      └────────────────────────────────────┘
                                        ▲
                                        |
                                        |
                                        │ background probes (/probe)
                                        |
                                        |
                  ------------------------------------------------
                  |                                              |
                  |                                              |
                  |                                              |
                  ▼                                              ▼
       ┌────────────────────────┐                    ┌────────────────────────┐
       │     REPLICA POD A      │                    │      REPLICA POD B     │
       │────────────────────────│                    │────────────────────────│
       │ App Server (/handle)   │                    │ App Server (/handle)   │
       │ RIF Middleware         │                    │ RIF Middleware         │
       │   - increment before   │                    │   - increment before   │
       │     processing request │                    │     processing request │
       │   - decrement after    │                    │   - decrement after    │
       │     sending response   │                    │     sending response   │
       │ /probe endpoint        │                    │ /probe endpoint        │
       │   - returns RIF        │                    │   - returns RIF        │
       └────────────────────────┘                    └────────────────────────┘
```

## Workflow

The following steps describe how OpenPrequal handles requests and maintains backend health:

### Step 1: Client sends request
Client sends an HTTP request to the proxy's `/proxy` endpoint. The proxy acts as the entry point for all traffic.
```text
       CLIENT
       │
       │  HTTP Request (/proxy)
       ▼
       Prequal Sidecar (Origin Pod)
```

### Step 2: Sidecar chooses best replica
The Replica Selector reads real-time RIF and latency data from the Probe Manager and selects the backend with the lowest load and latency (using HCL order for tie-breaking).
```text
       [Replica Selector]
       │ Reads RIF + latency data from Probe Manager
       │ Picks replica with lowest (RIF, latency) in HCL order
       ▼
       [Proxy Handler]
       │
       │  Forward request to chosen replica's /handle endpoint
       ▼
```

### Step 3: Replica processes request
The chosen backend increments its RIF counter, processes the request, and decrements the counter after responding. This ensures accurate load tracking.
```text
       Replica Pod (e.g., Replica A)
       │
       ├─> RIF Middleware
       │     - Increment RIF counter
       │     - Pass request to app handler
       │
       ├─> Application handler processes request
       │
       ├─> Send response back to sidecar
       │
       └─> RIF Middleware
              - Decrement RIF counter
```

### Step 4: Sidecar returns result to client
The proxy receives the response from the backend and returns it to the client, completing the request lifecycle.
```text
       Sidecar (Origin Pod)
       │ Receives response from replica
       │ Returns it to the client
       ▼
       CLIENT
```

### Background Process: Probing
The Probe Manager periodically sends GET requests to `/probe` on all backends. Each backend returns its current RIF and a timestamp. This data is used to update the probe pool and inform routing decisions.
```text
       [Probe Manager in Sidecar]
       ├─ Periodically sends GET /probe to all replicas
       ├─ /probe in replicas returns:
       │     {
       │       "rif": current_requests_in_flight,
       │       "timestamp": ...
       │     }
       └─ Updates local RIF + latency table for Replica Selector
```

## Probe Pool & Probing Architecture

- **Probe Pool:** Maintains recent probe results for each backend, including average latency, RIF values, and probe timestamps. The probe pool is used by the load balancer to make routing decisions, detect overloaded or unhealthy backends, and optimize traffic distribution.
- **Probe Manager:** Consumes probe tasks from a queue, sends probe requests to backends, and updates the probe pool asynchronously (off the hot path). This ensures that health checks do not block request processing.
- **Task Queue:** Ensures probe requests are distributed and not repeated for the same backend until all have been probed (random selection without replacement). This avoids probe storms and balances monitoring load.
- **Prequal Load Balancer:** Classifies backends as hot/cold based on RIF values, chooses the cold backend with lowest latency, and schedules probe tasks for two randomly selected backends after each request. This approach minimizes latency and prevents overloading any single backend.

Backends register automatically with the proxy via periodic heartbeats, or can be registered manually. The proxy tracks backend health using heartbeat timeouts and a health check endpoint, and load balances requests to healthy backends. If a backend fails to respond to heartbeats or health checks, it is automatically removed from the routing pool until it recovers.

## Configuration

All configuration can be set via environment variables or by editing `src/config/config.py`. Environment variables override config file defaults, making it easy to customize deployments for different environments.

**Example usage:**
```sh
export PROXY_URL=http://localhost:8000
export BACKEND_PORT=8002
export LOAD_BALANCER_CLASS=algorithms.round_robin_load_balancer.RoundRobinLoadBalancer
```

**Configurable options:**
- `PROXY_URL`: Proxy URL for backend registration (default: `http://localhost:8000`)
- `BACKEND_PORT`: Port for backend server (default: `8001`)
- `BACKEND_URL`: Backend URL (default: `http://localhost:<BACKEND_PORT>`)
- `BACKEND_HEARTBEAT_SECONDS`: Heartbeat interval in seconds (default: `30`)
- `BACKEND_HEARTBEAT_TIMEOUT`: Heartbeat timeout in seconds (default: `2 * HEARTBEAT_SECONDS`)
- `LATENCY_WINDOW_SECONDS`: Window for average latency metrics (default: `300`)
- `BACKEND_HEALTH_PATH`: Path for health checks (default: `/probe`)
- `LOAD_BALANCER_CLASS`: Python path to the load balancer class (default: `algorithms.prequal_load_balancer.PrequalLoadBalancer`)
- `REGISTRY_CLASS`: Python path to the registry class (default: `core.backend_registry.BackendRegistry`)
- `CUSTOM_REGISTER_HOOK`, `CUSTOM_UNREGISTER_HOOK`, `CUSTOM_PATH_REWRITE`, `CUSTOM_REQUEST_HOOK`, `CUSTOM_RESPONSE_HOOK`: Python paths to custom hook functions (optional)

To use a custom load balancer or hook, set the corresponding environment variable to the Python path of your implementation.

## Usage

### Install Dependencies
Install all required Python packages:
```bash
pip install -r requirements.txt
```

### Start the Proxy
Start the API gateway on port 8000:
```bash
PYTHONPATH=src uvicorn proxy:app --port 8000
```
You should see Uvicorn startup logs and the proxy listening on port 8000.

### Start a Backend Example
Start a backend server that auto-registers with the proxy via heartbeat:
```bash
PROXY_URL=http://localhost:8000 BACKEND_PORT=8001 PYTHONPATH=src uvicorn server:app --port 8001
```
The backend will send heartbeats to the proxy and expose `/handle`, `/probe`, and `/metrics` endpoints.

### Manual Backend Registration
If not using heartbeat, you can register a backend manually:
```bash
curl -X POST http://localhost:8000/register -H 'Content-Type: application/json' -d '{"url": "http://localhost:8001", "port": 8001}'
```
You should receive a confirmation response from the proxy.

### Proxy Requests
Send a request to the proxy, which will route it to a healthy backend:
```bash
curl http://localhost:8000/
```
You should receive the backend's response.

### View Metrics
Prometheus metrics are available at:
```bash
curl http://localhost:8000/metrics   # Proxy metrics
curl http://localhost:8001/metrics   # Backend metrics
```
Metrics include request counts, error rates, latency, and RIF values for monitoring and alerting.

## Running from Source

Project structure:
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

### Add `src/` to your `PYTHONPATH`
This ensures all imports like `from config.config import Config` work as expected and avoids import errors common in Python projects with a `src/` layout.

**Example:**
```sh
PYTHONPATH=src uvicorn server:app --port 8001
PYTHONPATH=src uvicorn proxy:app --port 8000
```

Or use the provided scripts in `scripts/` for multi-backend startup:
```sh
bash scripts/start_backends.sh 3   # Starts proxy and 3 backends
```

#### Why?
This is the recommended approach for open source Python projects using a `src/` layout. It avoids import errors and makes your codebase more maintainable. If you encounter import errors, check that your working directory and PYTHONPATH are set correctly.

#### For Contributors
- Always run scripts and tests with `PYTHONPATH=src`.
- If using an IDE, set the working directory or source roots accordingly.
- All internal imports should be absolute (e.g., `from core.proxy_handler import ProxyHandler`).

## Docker & Kubernetes Deployment

OpenPrequal includes Dockerfiles for both proxy and backend, and a Helm chart for Kubernetes deployment. See `k8s/` for details. You can customize deployments by editing environment variables, Helm values, or Dockerfiles to match your infrastructure needs.

### Docker
Build and run the proxy and backend containers:
```sh
docker build -f k8s/openprequal/docker/Dockerfile.proxy -t openprequal-proxy .
docker build -f k8s/openprequal/docker/Dockerfile.backend -t openprequal-backend .
docker run -d --name openprequal-proxy -p 8000:8000 openprequal-proxy
docker run -d --name openprequal-backend1 -e PROXY_URL=http://host.docker.internal:8000 -e BACKEND_PORT=8001 -p 8001:8001 openprequal-backend
```
You can scale by running multiple backend containers with different ports.

### Kubernetes
Deploy with Helm:
```sh
cd k8s/openprequal
helm install openprequal .
```
Customize `values.yaml` to set replica counts, resource limits, and environment variables. The Helm chart creates deployments and services for both proxy and backend pods.

## Testing

OpenPrequal includes comprehensive unit tests for all core modules, algorithms, and integration points. Tests cover backend registration, health checks, load balancing, metrics, and error handling.

Run all tests with:
```bash
PYTHONPATH=src pytest tests/
```
To run a specific test file:
```bash
PYTHONPATH=src pytest tests/test_core.py
```
Test results will show passed/failed cases and coverage information.

## Extending

You can extend OpenPrequal by implementing your own load balancer or custom hooks:

- **Custom Load Balancer:** Subclass `LoadBalancer` in `src/abstractions/load_balancer.py` and implement the `select_backend` method. Example:
       ```python
       from abstractions.load_balancer import LoadBalancer
       class MyCustomBalancer(LoadBalancer):
              def select_backend(self, backends, probe_pool):
                     # Custom logic here
                     return backends[0]
       ```
       Set `LOAD_BALANCER_CLASS` to your class path.

- **Custom Hooks:** Implement Python functions for registration, path rewriting, or request/response processing. Set the corresponding environment variable to the function path (see Configuration section).

This allows you to adapt OpenPrequal to advanced routing, authentication, or transformation needs.

## License

MIT License. 
See LICENSE file for details.
