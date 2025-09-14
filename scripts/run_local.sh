#!/bin/bash
# Script to kill all backend and proxy servers started by start_backends.sh


mkdir -p logs/

# Kill all uvicorn processes running src.server:app or src.proxy:app
ps aux | grep 'uvicorn' | grep -E 'server:app|proxy:app' | grep -v grep | awk '{print $2}' | xargs -r kill

echo "Killed all backend and proxy servers. Waiting 20 seconds for processes to terminate..."

sleep 20

# Check if Redis is running, start if not
echo "Checking Redis status..."
if ! redis-cli ping >/dev/null 2>&1; then
  echo "Redis is not running. Please start Redis first:"
  echo "  macOS (with Homebrew): brew services start redis"
  echo "  Linux (systemd): sudo systemctl start redis"
  echo "  Manual start: redis-server"
  echo "  Docker: docker run -d --name redis -p 6379:6379 redis:7-alpine"
  echo ""
  echo "Starting Redis with Docker..."
  docker stop redis 2>/dev/null || true
  docker rm redis 2>/dev/null || true
  docker run -d --name redis -p 6379:6379 \
    -v redis_data:/data \
    redis:7-alpine redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
  
  echo "Waiting for Redis to start..."
  sleep 5
  
  # Verify Redis is running
  if ! redis-cli ping >/dev/null 2>&1; then
    echo "Failed to start Redis. Please start it manually."
    exit 1
  fi
fi

echo "✓ Redis is running"

# Set Redis environment variables
export REGISTRY_TYPE=redis
export REDIS_URL=redis://localhost:6379
export REDIS_DB=${REDIS_DB:-0}

echo "Using Redis database: $REDIS_DB"

# Script to start multiple backend servers on different ports


# Ensure port 8000 is free before starting the proxy server
if lsof -i :8000 -sTCP:LISTEN -t >/dev/null ; then
  echo "Port 8000 is still in use. Attempting to free it..."
  lsof -i :8000 -sTCP:LISTEN -t | xargs -r kill -9
  echo "Killed process(es) using port 8000. Waiting 2 seconds..."
  sleep 2
fi

if [ -z "$LOAD_BALANCER_CLASS" ]; then
  LOAD_BALANCER_CLASS="default"
fi
echo "Starting proxy server on port 8000 with LOAD_BALANCER_CLASS=$LOAD_BALANCER_CLASS"
nohup env PYTHONPATH=src LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" REGISTRY_TYPE="$REGISTRY_TYPE" REDIS_URL="$REDIS_URL" REDIS_DB="$REDIS_DB" .venv/bin/uvicorn proxy:app --port 8000 --workers 10 > logs/proxy_8000.log 2>&1 &

# Number of backend servers to start (default: 2)
NUM_SERVERS=${1:-20}
# Proxy URL (default: http://localhost:8000)
PROXY_URL=${2:-http://localhost:8000}
# Starting port (default: 8001)
START_PORT=${3:-8001}

for ((i=0; i<$NUM_SERVERS; i++)); do
  PORT=$((START_PORT + i))
  echo "Starting backend server on port $PORT"
  PROXY_URL=$PROXY_URL BACKEND_PORT=$PORT REGISTRY_TYPE="$REGISTRY_TYPE" REDIS_URL="$REDIS_URL" REDIS_DB="$REDIS_DB" nohup env PYTHONPATH=src .venv/bin/uvicorn server:app --port $PORT --workers 10 > logs/backend_$PORT.log 2>&1 &
done

echo "Started $NUM_SERVERS backend servers. Logs: backend_<PORT>.log"
echo "Redis UI available at: http://localhost:8081 (if you want to monitor Redis)"
echo "To start Redis UI: docker run -d --name redis-ui -p 8081:8081 -e REDIS_HOSTS=local:localhost:6379 rediscommander/redis-commander:latest"