docker build -f k8s/openprequal/docker/Dockerfile.proxy -t pranshug258/openprequal-proxy:latest .
docker build -f k8s/openprequal/docker/Dockerfile.server -t pranshug258/openprequal-server:latest .

docker push pranshug258/openprequal-proxy:latest
docker push pranshug258/openprequal-server:latest