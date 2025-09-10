#!/usr/bin/env python3
"""
Performance comparison of the old vs new health check approach.
"""
import asyncio
import time
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from contracts.backend import Backend
from core.backend_registry import BackendRegistry


async def test_performance():
    """Compare old vs new approach performance"""
    
    # Create registry with many backends
    registry = BackendRegistry()
    
    # Register 1000 backends
    backends = []
    for i in range(1000):
        backend = Backend(url=f"http://backend{i}:800{i % 10}", health=(i % 10 != 0))  # 10% unhealthy
        backends.append(backend)
        await registry.register(backend)
    
    print(f"Registered {len(backends)} backends")
    
    # Test the old approach (simulated)
    start_time = time.time()
    for _ in range(100):  # 100 requests
        all_backends = await registry.list_backends()
        backend_health = {b.url: b.health for b in all_backends}
        # Simulate checking health of one backend
        test_url = "http://backend500:8000"
        is_healthy = backend_health.get(test_url, False)
    old_time = time.time() - start_time
    
    # Test the new approach
    start_time = time.time()
    for _ in range(100):  # 100 requests
        is_healthy = await registry.is_backend_healthy("http://backend500:8000")
    new_time = time.time() - start_time
    
    print(f"\nPerformance comparison for 100 health checks:")
    print(f"Old approach (list_backends): {old_time:.4f} seconds")
    print(f"New approach (is_backend_healthy): {new_time:.4f} seconds")
    print(f"Improvement: {old_time / new_time:.1f}x faster")
    
    # Test accuracy
    old_result = backend_health.get("http://backend500:8000", False)
    new_result = await registry.is_backend_healthy("http://backend500:8000")
    print(f"\nAccuracy check:")
    print(f"Old result: {old_result}")
    print(f"New result: {new_result}")
    print(f"Results match: {old_result == new_result}")


if __name__ == "__main__":
    asyncio.run(test_performance())
