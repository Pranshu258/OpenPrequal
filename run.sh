#!/bin/bash
# Usage: ./run.sh <num_backends> <algorithm>
# Example: ./run.sh 3 roundrobin

set -e

NUM_BACKENDS=${1:-3}
ALGO=${2:-random}


# Kill existing backend and proxy processes
echo "Killing existing backend and proxy servers..."
pkill -f './backend' || true
pkill -f './proxy' || true
sleep 1

# Build backend and proxy
cd "$(dirname "$0")"
go build -o backend ./cmd/backend/main.go
go build -o proxy ./cmd/proxy/main.go

# Start backend servers
for ((i=1; i<=NUM_BACKENDS; i++)); do
    PORT=$((8080 + i))
    HOST=localhost PORT=$PORT nohup ./backend > backend_$PORT.log 2>&1 &
    echo "Started backend on port $PORT"
done

# Build backend URLs for proxy registry
BACKEND_URLS=""
for ((i=1; i<=NUM_BACKENDS; i++)); do
    PORT=$((8080 + i))
    BACKEND_URLS+="http://localhost:$PORT,"
done
BACKEND_URLS=${BACKEND_URLS%,} # Remove trailing comma

# Run proxy
REGISTRY_TYPE=inmemory LOAD_BALANCER_TYPE=$ALGO BACKEND_URLS="$BACKEND_URLS" nohup ./proxy > proxy.log 2>&1 &
echo "Started proxy with $ALGO algorithm and $NUM_BACKENDS backends"
