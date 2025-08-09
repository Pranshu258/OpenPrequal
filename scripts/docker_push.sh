docker build -f Dockerfile.proxy -t pranshug258/openprequal-proxy:latest .
docker build -f Dockerfile.backend -t pranshug258/openprequal-backend:latest .

docker push pranshug258/openprequal-proxy:latest
docker push pranshug258/openprequal-backend:latest