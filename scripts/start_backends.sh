#!/bin/bash
# Script to start multiple backend servers on different ports

# Number of backend servers to start (default: 2)
NUM_SERVERS=${1:-2}
# Proxy URL (default: http://localhost:8000)
PROXY_URL=${2:-http://localhost:8000}
# Starting port (default: 8001)
START_PORT=${3:-8001}


for ((i=0; i<$NUM_SERVERS; i++)); do
  PORT=$((START_PORT + i))
  echo "Starting backend server on port $PORT (registering with $PROXY_URL)"
  PROXY_URL=$PROXY_URL BACKEND_PORT=$PORT nohup uvicorn src.server:app --port $PORT > logs/backend_$PORT.log 2>&1 &
done

echo "Started $NUM_SERVERS backend servers. Logs: backend_<PORT>.log"
# Start the proxy server
echo "Starting proxy server on port 8000"
nohup uvicorn src.proxy:app --port 8000 > logs/backend_8000.log 2>&1 &
