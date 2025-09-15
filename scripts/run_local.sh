#!/bin/bash
# Script to kill all backend and proxy servers started by start_backends.sh


mkdir -p logs/

# Kill all uvicorn processes running src.server:app or src.proxy:app
killall Python
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
  echo "Starting local redis-server (preferred for local testing)..."
  # Try Homebrew/service first
  if command -v brew >/dev/null 2>&1 && brew services list | grep -q redis; then
    echo "Starting Redis via Homebrew services..."
    brew services start redis || true
  elif command -v systemctl >/dev/null 2>&1; then
    echo "Starting Redis via systemctl..."
    sudo systemctl start redis || true
  elif command -v redis-server >/dev/null 2>&1; then
    echo "Launching redis-server in background with temporary data dir..."
    REDIS_DIR="${REDIS_DIR:-$(mktemp -d /tmp/openprequal-redis-XXXX)}"
    redis-server --dir "$REDIS_DIR" --appendonly yes --daemonize yes || {
      echo "[ERROR] Failed to start redis-server locally."
      exit 1
    }
  else
    echo "Redis not found. Please install Redis or start it manually. Examples:" \
         "\n  macOS (Homebrew): brew install redis && brew services start redis" \
         "\n  Linux (systemd): sudo apt install redis-server && sudo systemctl start redis" \
         "\n  Manual: redis-server"
    exit 1
  fi

  echo "Waiting for Redis to accept PING..."
  for i in {1..15}; do
    if redis-cli ping >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if ! redis-cli ping >/dev/null 2>&1; then
    echo "Failed to detect running Redis after startup attempts. Please start Redis manually." 
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

if [ -z "$1" ]; then
  LOAD_BALANCER_CLASS="default"
else
  LOAD_BALANCER_CLASS="$1"
fi
echo "Starting proxy server on port 8000 with LOAD_BALANCER_CLASS=$LOAD_BALANCER_CLASS"
nohup env PYTHONPATH=src LOAD_BALANCER_CLASS="$LOAD_BALANCER_CLASS" REGISTRY_TYPE="$REGISTRY_TYPE" REDIS_URL="$REDIS_URL" REDIS_DB="$REDIS_DB" .venv/bin/uvicorn proxy:app --port 8000 > logs/proxy_8000.log 2>&1 &
PROXY_PID=$!
sleep 1
if ! kill -0 "$PROXY_PID" >/dev/null 2>&1; then
  echo "[ERROR] Failed to start proxy; check logs/proxy_8000.log"
else
  # disown if shell supports it
  (disown "$PROXY_PID" 2>/dev/null) || true
fi

# Number of backend servers to start (default: 2)
NUM_SERVERS=${2:-100}
# Proxy URL (default: http://localhost:8000)
PROXY_URL=${3:-http://localhost:8000}
# Starting port (default: 8001)
START_PORT=${4:-8001}

for ((i=0; i<$NUM_SERVERS; i++)); do
  PORT=$((START_PORT + i))
  echo "Starting backend server on port $PORT"
  nohup env PYTHONPATH=src PROXY_URL=$PROXY_URL BACKEND_PORT=$PORT REGISTRY_TYPE="$REGISTRY_TYPE" REDIS_URL="$REDIS_URL" REDIS_DB="$REDIS_DB" .venv/bin/uvicorn server:app --port $PORT > logs/backend_$PORT.log 2>&1 &
  BACK_PID=$!
  sleep 0.2
  if ! kill -0 "$BACK_PID" >/dev/null 2>&1; then
    echo "[WARN] Backend on port $PORT failed to start. See logs/backend_$PORT.log"
  else
    (disown "$BACK_PID" 2>/dev/null) || true
  fi
done

echo "Started $NUM_SERVERS backend servers. Logs: backend_<PORT>.log"
echo "Redis UI available at: http://localhost:8081 (if you want to monitor Redis)"
echo "To start Redis UI: docker run -d --name redis-ui -p 8081:8081 -e REDIS_HOSTS=local:localhost:6379 rediscommander/redis-commander:latest"
