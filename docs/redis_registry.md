# Redis Backend Registry

This document explains how to use the Redis-based backend registry implementation.

## Overview

The `RedisBackendRegistry` provides a Redis-backed implementation of the backend registry, offering persistence and scalability advantages over the in-memory implementation.

## Features

- **Persistent Storage**: Backend registrations survive application restarts
- **Scalability**: Multiple proxy instances can share the same registry
- **Heartbeat Management**: Automatic health checking based on heartbeat timeouts
- **Metrics Tracking**: Store and update backend performance metrics
- **Cleanup**: Automatic cleanup of expired backends

## Configuration

### Environment Variables

Set these environment variables to configure Redis usage:

```bash
# Registry type selection
REGISTRY_TYPE=redis  # or "memory" for in-memory registry

# Redis connection
REDIS_URL=redis://localhost:6379
REDIS_DB=0

# Heartbeat configuration (optional)
BACKEND_HEARTBEAT_TIMEOUT=60
```

### Redis Setup

1. **Install Redis** (if not already installed):
   ```bash
   # macOS
   brew install redis
   
   # Ubuntu/Debian
   sudo apt-get install redis-server
   
   # CentOS/RHEL
   sudo yum install redis
   ```

2. **Start Redis**:
   ```bash
   # macOS (with Homebrew)
   brew services start redis
   
   # Linux (systemd)
   sudo systemctl start redis
   
   # Manual start
   redis-server
   ```

3. **Verify Redis is running**:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

## Dependencies

Install the required Python packages:

```bash
pip install redis aioredis
```

These are already included in the updated `requirements.txt`.

## Usage

### Using the Factory (Recommended)

```python
from core.registry_factory import RegistryFactory

# Create registry based on environment configuration
registry = RegistryFactory.create_registry()

# Or explicitly specify Redis
registry = RegistryFactory.create_registry(
    registry_type="redis",
    redis_url="redis://localhost:6379",
    redis_db=0
)
```

### Direct Instantiation

```python
from core.redis_backend_registry import RedisBackendRegistry

registry = RedisBackendRegistry(
    redis_url="redis://localhost:6379",
    heartbeat_timeout=60,
    db=0
)
```

### Basic Operations

```python
from contracts.backend import Backend

# Create a backend
backend = Backend(url="http://api.example.com", port=8001, health=True)

# Register backend
result = await registry.register(backend)

# List all backends
backends = await registry.list_backends()

# Update backend health
await registry.update_backend_health(backend, False)

# Update backend metrics
await registry.update_backend_metrics(
    backend,
    in_flight_requests=10.0,
    rif_avg_latency=150.5,
    overall_avg_latency=145.2
)

# Unregister backend
result = await registry.unregister(backend)

# Cleanup expired backends
await registry.cleanup_expired_backends()

# Close connection when done
await registry.close()
```

### Context Manager Usage

```python
async with RedisBackendRegistry() as registry:
    # Use registry
    await registry.register(backend)
    backends = await registry.list_backends()
    # Connection automatically closed when exiting context
```

## Redis Data Structure

The registry stores data in Redis using the following key patterns:

- **Backends**: `backend:{url}:{port}` → JSON serialized Backend object
- **Heartbeats**: `heartbeat:{url}:{port}` → Unix timestamp

Example:
```
backend:http://api.example.com:8001 → {"url": "http://api.example.com", "port": 8001, "health": true, ...}
heartbeat:http://api.example.com:8001 → 1694234567.123
```

## Migration from In-Memory Registry

1. **Update requirements**: Install Redis dependencies
   ```bash
   pip install redis aioredis
   ```

2. **Set environment variable**:
   ```bash
   export REGISTRY_TYPE=redis
   export REDIS_URL=redis://localhost:6379
   ```

3. **Update code** (if using direct instantiation):
   ```python
   # Old
   from core.backend_registry import BackendRegistry
   registry = BackendRegistry()
   
   # New
   from core.registry_factory import RegistryFactory
   registry = RegistryFactory.create_registry()
   ```

4. **Start Redis server** before running your application

## Performance Considerations

- **Connection Pooling**: aioredis handles connection pooling automatically
- **Database Selection**: Use different Redis databases for different environments
- **Cleanup**: Run periodic cleanup to remove expired backends
- **Monitoring**: Monitor Redis memory usage and performance

## Testing

Run the test script to verify Redis functionality:

```bash
python test_redis_registry.py
```

This will test all registry operations and verify Redis connectivity.

## Troubleshooting

### Connection Issues

1. **Redis not running**:
   ```bash
   redis-cli ping
   # If no response, start Redis server
   ```

2. **Connection timeout**:
   - Check Redis URL and port
   - Verify firewall settings
   - Check Redis configuration for bind address

3. **Authentication errors**:
   - If Redis requires authentication, include password in URL:
     `redis://:password@localhost:6379`

### Performance Issues

1. **High memory usage**:
   - Implement regular cleanup of expired backends
   - Consider using Redis TTL for automatic expiration

2. **Slow operations**:
   - Monitor Redis performance
   - Consider Redis clustering for high load

### Data Corruption

1. **Invalid JSON data**:
   - The registry automatically cleans up corrupted entries
   - Check logs for warnings about data parsing failures

## Production Deployment

For production use, consider:

1. **Redis Persistence**: Configure Redis persistence (RDB/AOF)
2. **High Availability**: Use Redis Sentinel or Cluster
3. **Monitoring**: Monitor Redis metrics and logs
4. **Backup**: Regular backup of Redis data
5. **Security**: Configure Redis authentication and network security
