#!/bin/bash

set -e

# Get load balancer class from command line argument or use default
LOAD_BALANCER_CLASS=${1:-"default"}
# Get number of backend servers from command line argument or use default
NUM_SERVERS=${2:-20}

# Set the base directory to the location of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}" )" && pwd)"
CHART_DIR="$SCRIPT_DIR/../k8s/openprequal"

cd "$CHART_DIR"

echo "Installing OpenPrequal with load balancer: $LOAD_BALANCER_CLASS and $NUM_SERVERS backend servers"
helm upgrade --install openprequal . \
  --set proxy.env.LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" \
  --set server.replicaCount="$NUM_SERVERS"

echo "Waiting for pods to be ready..."
kubectl wait --for=condition=Ready pod -l app=openprequal-server --timeout=120s || true
kubectl wait --for=condition=Ready pod -l app=openprequal-proxy --timeout=120s || true

echo "Installing Prometheus..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install prometheus prometheus-community/prometheus

echo "Installing Grafana..."
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm upgrade --install grafana grafana/grafana --namespace default --create-namespace

kubectl get secret --namespace default grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

echo "All deployments applied and pods are ready."
kubectl get pods
kubectl get svc

kubectl port-forward svc/openprequal-proxy 8000:8000 &
kubectl port-forward svc/prometheus-server 9090:80 &
kubectl port-forward --namespace default service/grafana 3000:80 &
