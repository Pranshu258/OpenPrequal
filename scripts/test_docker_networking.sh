#!/bin/bash

# Test script to verify Docker networking between containers

NETWORK=openprequal-net

echo "Testing Docker networking for OpenPrequal..."

# Check if containers are running
echo "=== Container Status ==="
docker ps --filter "network=$NETWORK" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== Testing connectivity from proxy to servers ==="

# Test connectivity from proxy to server1
echo "Testing proxy -> server1:"
docker exec openprequal-proxy sh -c "curl -s http://openprequal-server1:8000/ || echo 'Connection failed'"

echo ""
echo "Testing proxy -> server2:"
docker exec openprequal-proxy sh -c "curl -s http://openprequal-server2:8000/ || echo 'Connection failed'"

echo ""
echo "=== Testing probe endpoint from proxy ==="

# Test probe endpoint
echo "Testing proxy -> server1 probe:"
docker exec openprequal-proxy sh -c "curl -s http://openprequal-server1:8000/probe || echo 'Probe failed'"

echo ""
echo "Testing proxy -> server2 probe:"
docker exec openprequal-proxy sh -c "curl -s http://openprequal-server2:8000/probe || echo 'Probe failed'"

echo ""
echo "=== Testing from host to containers ==="

# Test from host
echo "Testing host -> proxy:"
curl -s http://localhost:8000/ || echo "Connection to proxy failed"

echo ""
echo "Testing host -> server1:"
curl -s http://localhost:8001/ || echo "Connection to server1 failed"

echo ""
echo "Testing host -> server2:"
curl -s http://localhost:8002/ || echo "Connection to server2 failed"

echo ""
echo "=== Recent logs ==="

echo "Proxy logs (last 10 lines):"
docker logs openprequal-proxy --tail 10

echo ""
echo "Server1 logs (last 10 lines):"
docker logs openprequal-server1 --tail 10

echo ""
echo "Server2 logs (last 10 lines):"
docker logs openprequal-server2 --tail 10

echo ""
echo "=== Network details ==="
docker network inspect $NETWORK --format "{{.IPAM.Config}}"
docker inspect openprequal-proxy --format "{{.NetworkSettings.Networks.$NETWORK.IPAddress}}"
docker inspect openprequal-server1 --format "{{.NetworkSettings.Networks.$NETWORK.IPAddress}}"
docker inspect openprequal-server2 --format "{{.NetworkSettings.Networks.$NETWORK.IPAddress}}"
