#!/bin/bash
# File: test.sh
set -e

# Install minikube if not present
if ! command -v minikube &> /dev/null; then
  echo "Minikube not found. Installing..."
  curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
  sudo install minikube-linux-amd64 /usr/local/bin/minikube
  rm minikube-linux-amd64
fi

# Install kubectl if not present
if ! command -v kubectl &> /dev/null; then
  echo "kubectl not found. Installing..."
  curl -LO "https://dl.k8s.io/release/$(curl -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
  rm kubectl
fi

# Install helm if not present
if ! command -v helm &> /dev/null; then
  echo "Helm not found. Installing..."
  curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
fi

# Start Minikube
minikube start

# Enable ingress addon
minikube addons enable ingress

# Deploy Prometheus stack (optional)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install prometheus prometheus-community/kube-prometheus-stack || true

# Package and install OpenPrequal chart
cd helm
helm package openprequal
cd ..
helm install openprequal ./helm/openprequal-0.1.0.tgz

# Wait for pods
kubectl rollout status deployment/openprequal-openprequal

# Port forward to access services locally
kubectl port-forward svc/openprequal-openprequal 8080:80 &

# Give some time for sidecar to come up
sleep 10

# Test endpoints
curl -s http://localhost:8080/probe
curl -s http://localhost:8080/metrics

# Done
echo "✅ OpenPrequal sidecar deployed and test completed!"
