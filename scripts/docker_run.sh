docker run -d --name openprequal-proxy -p 8000:8000 pranshug258/openprequal-proxy:latest

docker run -d --name openprequal-backend1 \
  -e PROXY_URL=http://host.docker.internal:8000 \
  -e BACKEND_PORT=8001 \
  -p 8001:8001 \
  pranshug258/openprequal-backend:latest

docker run -d --name openprequal-backend2 \
  -e PROXY_URL=http://host.docker.internal:8000 \
  -e BACKEND_PORT=8002 \
  -p 8002:8002 \
  pranshug258/openprequal-backend:latest