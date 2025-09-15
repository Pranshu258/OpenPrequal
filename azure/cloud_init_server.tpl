#cloud-config
package_update: true
package_upgrade: true
packages:
  - git
  - python3
  - python3-venv

runcmd:
  - [ bash, -lc, 'set -e
      cd /tmp
      if [ ! -d openprequal ]; then git clone https://github.com/Pranshu258/OpenPrequal.git openprequal; fi
      cd openprequal
      python3 -m venv .venv
      . .venv/bin/activate
      pip install --upgrade pip
      pip install -r requirements.txt
      export PYTHONPATH=src
      # Start server on $PORT and register to proxy
      nohup env PYTHONPATH=src PROXY_URL="http://4.246.77.106" BACKEND_PORT=$PORT .venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2 > ./logs/backend.log 2>&1 &
      # attempt registration via heartbeat client (server app will try as well)
      sleep 3
      curl -s -X POST "$PROXY_URL/register" -H 'Content-Type: application/json' -d "{\"url\": \"http://$(hostname -I | awk '{print $1}')\", \"port\": $PORT, \"health\": true}" || true
'
