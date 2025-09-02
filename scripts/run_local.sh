#!/bin/bash
# Script to stop and start the Go proxy and backend servers locally

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p logs/



# Kill all processes listening on port 8000 (proxy) and backend ports (8001-8020 by default)
echo "Killing any processes on port 8000 (proxy) and backend ports (8001-8020 by default)"
lsof -i :8000 -sTCP:LISTEN -t | xargs -r kill -9
for PORT in {8001..8020}; do
  lsof -i :$PORT -sTCP:LISTEN -t | xargs -r kill -9
done

# Remove any lingering pid files
rm -f logs/pids_proxy.pid logs/backend_*.pid

echo "Stopped previous local servers. Waiting 2 seconds..."
sleep 2

# Algorithm selection: pass as first argument, fallback to env, fallback to default
ALGO_ARG="${1-}"
case "$ALGO_ARG" in
  round_robin|random|least_latency|least_latency_p2|least_rif|least_rif_p2|default|prequal)
    LOAD_BALANCER_CLASS="$ALGO_ARG"
    shift
    ;;
  "")
    if [ -z "${LOAD_BALANCER_CLASS-}" ]; then
      LOAD_BALANCER_CLASS="default"
    fi
    ;;
  *)
    # Not a recognized algorithm, treat as number of servers
    if [ -z "${LOAD_BALANCER_CLASS-}" ]; then
      LOAD_BALANCER_CLASS="default"
    fi
    ;;
esac

echo "Starting Go proxy (port 8000) with LOAD_BALANCER_CLASS=$LOAD_BALANCER_CLASS"
# run from go/ module dir so the go tool finds go.mod
(
  cd "$ROOT_DIR/go" || exit 1
  env LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" nohup go run ./cmd/proxy > "$ROOT_DIR/logs/backend_8000.log" 2>&1
) &
PROXY_PID=$!
echo "$PROXY_PID" > logs/pids_proxy.pid

# give the proxy a moment to start so backends can register reliably
sleep 0.5

# Number of backend servers to start (default: 20)
NUM_SERVERS=${1:-20}
# Proxy URL (default: http://localhost:8000)
PROXY_URL=${2:-http://localhost:8000}
# Starting port (default: 8001)
START_PORT=${3:-8001}

for ((i=0; i<NUM_SERVERS; i++)); do
  PORT=$((START_PORT + i))
  echo "Starting Go backend server on port $PORT"
  # run server from module root so go tool finds go.mod
  (
    cd "$ROOT_DIR/go" || exit 1
    PROXY_URL=$PROXY_URL BACKEND_PORT=$PORT nohup env go run ./cmd/server > "$ROOT_DIR/logs/backend_$PORT.log" 2>&1
  ) &
  BACKEND_PID=$!
  echo "$BACKEND_PID" > logs/backend_$PORT.pid
done

echo "Started $NUM_SERVERS backend servers. Logs: logs/backend_<PORT>.log"
echo "Started $NUM_SERVERS backend servers. Logs: $ROOT_DIR/logs/backend_<PORT>.log"