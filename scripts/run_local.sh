#!/bin/bash
# Script to kill all backend and proxy servers started by start_backends.sh

mkdir logs/

# Kill all uvicorn processes running src.server:app or src.proxy:app
ps aux | grep 'uvicorn' | grep -E 'server:app|proxy:app' | grep -v grep | awk '{print $2}' | xargs -r kill

echo "Killed all backend and proxy servers."

# Script to start multiple backend servers on different ports

# Start the proxy server
echo "Starting proxy server on port 8000 with LOAD_BALANCER_CLASS=$LOAD_BALANCER_CLASS"
nohup env PYTHONPATH=src LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" uvicorn proxy:app --port 8000 > logs/backend_8000.log 2>&1 &

# Number of backend servers to start (default: 2)
NUM_SERVERS=${1:-2}
# Proxy URL (default: http://localhost:8000)
PROXY_URL=${2:-http://localhost:8000}
# Starting port (default: 8001)
START_PORT=${3:-8001}

for ((i=0; i<$NUM_SERVERS; i++)); do
  PORT=$((START_PORT + i))
  echo "Starting backend server on port $PORT"
  PROXY_URL=$PROXY_URL BACKEND_PORT=$PORT nohup env PYTHONPATH=src uvicorn server:app --port $PORT > logs/backend_$PORT.log 2>&1 &
done

echo "Started $NUM_SERVERS backend servers. Logs: backend_<PORT>.log"
