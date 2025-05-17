# OpenPrequal
OpenPrequal is a distributed, Kubernetes-native sidecar load balancer based on the [Prequal](https://www.usenix.org/system/files/nsdi24-wydrowski.pdf) algorithm. It uses asynchronous probing and Requests-In-Flight (RIF) metrics to make low-latency routing decisions.

---

## 🚀 Features
- Hot-Cold Lexicographic (HCL) routing
- Real-time RIF tracking
- Asynchronous probing across replicas
- Prometheus metrics export
- Helm chart deployment

---

## 🧪 Quick Start (with Minikube)

```bash
chmod +x test.sh
./test.sh
```

This installs:
- Minikube, kubectl, Helm (if not installed)
- Prometheus monitoring stack
- The OpenPrequal sidecar via Helm

---

## 🛠 Manual Deployment

### 1. Start Minikube
```bash
minikube start
minikube addons enable ingress
```

### 2. Install Chart
```bash
cd helm
helm package openprequal
cd ..
helm install openprequal ./helm/openprequal-0.1.0.tgz
```

---

## 📈 Metrics
Metrics available at `/metrics`:
- `prequal_proxy_requests_total`
- `prequal_probe_requests_total`
- `prequal_rif`

You can scrape them using Prometheus + ServiceMonitor.

---

## ⚙️ Configuration
Edit `values.yaml`:
```yaml
env:
  PROBE_RATE: "2"
  PROBE_TIMEOUT_MS: "100"
  QRIF_THRESHOLD: "0.75"
  MAX_PROBE_POOL: "16"
  REPLICA_LIST: "replica-a:8080,replica-b:8080"
```

---

## 🧪 Testing Load Balancer
1. Deploy mock replicas (e.g., `hashicorp/http-echo`)
2. Configure `REPLICA_LIST` to point to them
3. Send requests:
```bash
curl -X POST http://localhost:8080/proxy
```
4. Observe routing and metrics

---

## 📦 Packaging for Cloud
To publish:
- Build a container: `docker build -t yourname/openprequal .`
- Push to DockerHub or GHCR
- Add to AWS/GCP/Azure Marketplace via Helm or Operator Hub

---

## 🤝 Contributing
Feel free to open issues, PRs, or suggestions.

---

## 📄 License
MIT © Pranshu Gupta
