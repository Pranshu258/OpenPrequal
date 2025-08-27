#!/bin/bash

# Get load balancer class from command line argument or use default
LOAD_BALANCER_CLASS=${1:-"default"}
# Get number of backend servers from command line argument or use default
NUM_SERVERS=${2:-20}

echo "Using load balancer class: $LOAD_BALANCER_CLASS"
echo "Starting $NUM_SERVERS backend servers"

docker build -f k8s/openprequal/docker/Dockerfile.proxy -t pranshug258/openprequal-proxy:latest .
docker build -f k8s/openprequal/docker/Dockerfile.server -t pranshug258/openprequal-server:latest .

docker push pranshug258/openprequal-proxy:latest
docker push pranshug258/openprequal-server:latest

# Stop and remove existing containers
echo "Stopping and removing existing containers..."
docker stop openprequal-proxy $(for i in $(seq 1 $NUM_SERVERS); do echo "openprequal-server$i"; done) 2>/dev/null || true
docker rm openprequal-proxy $(for i in $(seq 1 $NUM_SERVERS); do echo "openprequal-server$i"; done) 2>/dev/null || true

# Use a user-defined Docker network for inter-container communication
NETWORK=openprequal-net
# Create the network if it doesn't exist
docker network inspect $NETWORK >/dev/null 2>&1 || docker network create $NETWORK

# Start proxy on the network
docker run -d --name openprequal-proxy --network $NETWORK -p 8000:8000 \
  -e LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" \
  pranshug258/openprequal-proxy:latest

# Wait for proxy to be ready
echo "Waiting for proxy to start..."
sleep 5

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

# Wait for services to be ready
echo "Waiting for all services to start..."
sleep 10

# Show container status
echo "Container status:"
docker ps --filter "network=$NETWORK"

# Check logs for any errors
echo "Checking proxy logs:"
docker logs openprequal-proxy --tail 20

# Check logs for all backend servers
for i in $(seq 1 $NUM_SERVERS); do
  SERVER_NAME="openprequal-server$i"
  echo "Checking $SERVER_NAME logs:"
  docker logs $SERVER_NAME --tail 20
done