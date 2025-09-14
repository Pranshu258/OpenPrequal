#!/bin/bash

# Fail fast, treat unset vars as errors, and make pipelines fail on first error
set -euo pipefail
IFS=$'\n\t'

# verify docker is available
command -v docker >/dev/null 2>&1 || { echo "docker is required but not found in PATH" >&2; exit 1; }

# Get load balancer class from command line argument or use default
LOAD_BALANCER_CLASS=${1:-"default"}
# Get number of backend servers from command line argument or use default
NUM_SERVERS=${2:-20}

echo "Using load balancer class: $LOAD_BALANCER_CLASS"
echo "Starting $NUM_SERVERS backend servers"

# Build images
docker build -f k8s/openprequal/docker/Dockerfile.proxy --build-arg LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" -t pranshug258/openprequal-proxy:latest .
docker build -f k8s/openprequal/docker/Dockerfile.server -t pranshug258/openprequal-server:latest .
docker build -f k8s/openprequal/docker/Dockerfile.redis -t pranshug258/openprequal-redis:latest k8s/openprequal/docker

# Optional: push images to registry if desired (uncomment to enable)
# docker push pranshug258/openprequal-proxy:latest
# docker push pranshug258/openprequal-server:latest

# Stop and remove existing containers (ignore errors)
echo "Stopping and removing existing containers..."
docker stop openprequal-proxy $(for i in $(seq 1 $NUM_SERVERS); do echo "openprequal-server$i"; done) 2>/dev/null || true
docker rm openprequal-proxy $(for i in $(seq 1 $NUM_SERVERS); do echo "openprequal-server$i"; done) 2>/dev/null || true
docker rm -f openprequal-redis 2>/dev/null || true

# Use a user-defined Docker network for inter-container communication
NETWORK=openprequal-net
# Create the network if it doesn't exist
docker network inspect $NETWORK >/dev/null 2>&1 || docker network create $NETWORK

# Start Redis container
REDIS_CONTAINER=openprequal-redis
echo "Starting Redis ($REDIS_CONTAINER)..."
# Build local redis image so no external pull is required (already built above)
docker run -d --name "$REDIS_CONTAINER" --network "$NETWORK" -v openprequal-redis-data:/data pranshug258/openprequal-redis:latest

echo "Waiting for Redis to be ready..."
# Wait until redis replies to PING, timeout after ~30s
for i in {1..15}; do
  docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1 && break
  sleep 2
done

if ! docker exec "$REDIS_CONTAINER" redis-cli ping >/dev/null 2>&1; then
  echo "Redis did not become ready in time. See container logs for details."
  docker logs "$REDIS_CONTAINER" --tail 50
  exit 1
fi

docker run -d --name openprequal-proxy --network $NETWORK -p 8000:8000 \
  -e REGISTRY_TYPE=redis \
  -e REDIS_URL=redis://$REDIS_CONTAINER:6379 \
  -e REDIS_DB=0 \
  -e LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" \
  pranshug258/openprequal-proxy:latest

echo "Proceeding to start backends."

# Start backend servers dynamically based on NUM_SERVERS parameter
echo "Starting $NUM_SERVERS backend servers..."
for i in $(seq 1 $NUM_SERVERS); do
  SERVER_NAME="openprequal-server$i"
  SERVER_PORT=$((8000 + i))
  
  echo "Starting $SERVER_NAME on port $SERVER_PORT..."
  docker run -d --name $SERVER_NAME --network $NETWORK \
    -e PROXY_URL=http://openprequal-proxy:8000 \
    -e BACKEND_HOST=$SERVER_NAME \
    -e BACKEND_PORT=8000 \
    -p $SERVER_PORT:8000 \
    pranshug258/openprequal-server:latest
done

# Wait a little for backends
echo "Waiting for all services to start..."
sleep 5

# Show container status
echo "Container status:"
docker ps --filter "network=$NETWORK"

# Check logs for any immediate errors
echo "Checking proxy logs:"
docker logs openprequal-proxy --tail 20

# Check logs for a few backend servers (first 5 and last 5 if many)
for i in $(seq 1 $( [ $NUM_SERVERS -le 10 ] && echo $NUM_SERVERS || echo 5 )); do
  SERVER_NAME="openprequal-server$i"
  echo "Checking $SERVER_NAME logs:"
  docker logs $SERVER_NAME --tail 20
done

if [ $NUM_SERVERS -gt 10 ]; then
  for i in $(seq $((NUM_SERVERS-4)) $NUM_SERVERS); do
    SERVER_NAME="openprequal-server$i"
    echo "Checking $SERVER_NAME logs:"
    docker logs $SERVER_NAME --tail 20
  done
fi