# What is the better approach, a probe from proxy to backend or a heartbeat from backend to proxy?

Both approaches—proxy-to-backend probe (active health check) and backend-to-proxy heartbeat (self-registration)—are used in distributed systems, and each has pros and cons:

**Heartbeat from backend to proxy (your current approach):**
- Pros:
  - Backends can register/unregister themselves dynamically.
  - Works well in environments where backends may scale up/down or have dynamic IPs.
  - Proxy does not need to know all possible backend addresses in advance.
- Cons:
  - Proxy may not know if a backend is truly healthy (only that it sent a heartbeat).
  - If a backend crashes between heartbeats, proxy may route traffic to a dead backend until the next missed heartbeat.

**Probe from proxy to backend (active health check):**
- Pros:
  - Proxy can detect backend health in real time and avoid routing to unhealthy instances.
  - Centralized health logic; proxy can remove dead/unresponsive backends quickly.
- Cons:
  - Proxy must know all backend addresses (or have a discovery mechanism).
  - More network traffic from frequent health checks, especially at scale.

**Best practice:**  
- Combine both: Use backend heartbeats for registration/deregistration, and have the proxy periodically probe registered backends for health. This ensures the proxy only routes to healthy, live backends and can quickly remove dead ones.

Let me know if you want to implement proxy-side health checks or need a hybrid solution!