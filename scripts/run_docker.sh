docker build -f k8s/openprequal/docker/Dockerfile.proxy -t pranshug258/openprequal-proxy:latest .
docker build -f k8s/openprequal/docker/Dockerfile.server -t pranshug258/openprequal-server:latest .

docker push pranshug258/openprequal-proxy:latest
docker push pranshug258/openprequal-server:latest

docker stop openprequal-proxy openprequal-server1 openprequal-server2
docker rm openprequal-proxy openprequal-server1 openprequal-server2

# Use a user-defined Docker network for inter-container communication
NETWORK=openprequal-net
# Create the network if it doesn't exist
docker network inspect $NETWORK >/dev/null 2>&1 || docker network create $NETWORK

# Start proxy on the network
docker run -d --name openprequal-proxy --network $NETWORK -p 8000:8000 pranshug258/openprequal-proxy:latest

# Start backend servers on the same network, using container names for backend registration
docker run -d --name openprequal-server1 --network $NETWORK \
  -e PROXY_URL=http://openprequal-proxy:8000 \
  -e BACKEND_HOST=openprequal-server1 \
  -e BACKEND_PORT=8000 \
  -p 8001:8000 \
  pranshug258/openprequal-server:latest

docker run -d --name openprequal-server2 --network $NETWORK \
  -e PROXY_URL=http://openprequal-proxy:8000 \
  -e BACKEND_HOST=openprequal-server2 \
  -e BACKEND_PORT=8000 \
  -p 8002:8000 \
  pranshug258/openprequal-server:latest