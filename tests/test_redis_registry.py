"""
Test script for Redis backend registry implementation.
"""
import asyncio
import logging
import time

from contracts.backend import Backend
from core.redis_backend_registry import RedisBackendRegistry

logging.basicConfig(level=logging.INFO)


async def test_redis_registry():
    """
    Test the Redis backend registry functionality.
    """
    print("Testing Redis Backend Registry...")
    
    # Initialize registry
    registry = RedisBackendRegistry(
        redis_url="redis://localhost:6379",
        heartbeat_timeout=5,
        db=1  # Use a test database
    )
    
    try:
        # Test connection
        await registry._get_redis()
        print("✓ Redis connection successful")
        
        # Create test backends
        backend1 = Backend(url="http://test1.com", port=8001, health=True)
        backend2 = Backend(url="http://test2.com", port=8002, health=True)
        
        # Test registration
        result1 = await registry.register(backend1)
        print(f"✓ Backend 1 registered: {result1['status']}")
        
        result2 = await registry.register(backend2)
        print(f"✓ Backend 2 registered: {result2['status']}")
        
        # Test listing
        backends = await registry.list_backends()
        print(f"✓ Listed {len(backends)} backends")
        for backend in backends:
            print(f"  - {backend}")
        
        # Test heartbeat timeout
        print("Waiting for heartbeat timeout...")
        await asyncio.sleep(6)  # Wait longer than timeout
        
        backends = await registry.list_backends()
        print(f"✓ After timeout, backends health status:")
        for backend in backends:
            print(f"  - {backend} (health: {backend.health})")
        
        # Test health update
        await registry.update_backend_health(backend1, True)
        print("✓ Updated backend 1 health to True")
        
        # Test metrics update
        await registry.update_backend_metrics(
            backend1,
            in_flight_requests=5.0,
            rif_avg_latency=100.5,
            overall_avg_latency=95.2
        )
        print("✓ Updated backend 1 metrics")
        
        backends = await registry.list_backends()
        for backend in backends:
            if backend.url == backend1.url:
                print(f"  - Updated backend: {backend}")
        
        # Test unregistration
        result = await registry.unregister(backend1)
        print(f"✓ Backend 1 unregistered: {result['status']}")
        
        backends = await registry.list_backends()
        print(f"✓ After unregister, {len(backends)} backends remain")
        
        # Test cleanup
        await registry.cleanup_expired_backends()
        print("✓ Cleanup completed")
        
        backends = await registry.list_backends()
        print(f"✓ After cleanup, {len(backends)} backends remain")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await registry.close()
        print("✓ Redis connection closed")


if __name__ == "__main__":
    asyncio.run(test_redis_registry())
