#cloud-config
package_update: true
package_upgrade: true
packages:
  - git
  - python3
  - python3-venv
  - redis-server

runcmd:
  - [ bash, -lc, 'set -e
      cd /tmp
      if [ ! -d openprequal ]; then git clone https://github.com/Pranshu258/OpenPrequal.git openprequal; fi
      cd openprequal
      python3 -m venv .venv
      . .venv/bin/activate
      pip install --upgrade pip
      pip install -r requirements.txt
      # start redis (system service installed by apt)
      sudo systemctl enable redis-server
      sudo systemctl start redis-server
      export PYTHONPATH=src
      # start proxy
      nohup env PYTHONPATH=src LOAD_BALANCER_CLASS="prequal" REGISTRY_TYPE="redis" REDIS_URL="redis://localhost:6379" REDIS_DB=0 .venv/bin/uvicorn proxy:app --host 0.0.0.0 --port 8000 --workers 4 > /var/log/proxy_8000.log 2>&1 &'
