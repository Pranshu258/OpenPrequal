"""
Example script showing how to use both memory and Redis registries.
"""
import asyncio
import os
from contracts.backend import Backend
from core.registry_factory import RegistryFactory


async def test_memory_registry():
    """Test the memory registry."""
    print("=== Testing Memory Registry ===")
    
    # Create memory registry
    registry = RegistryFactory.create_registry(registry_type="memory")
    
    # Create test backend
    backend = Backend(url="http://example.com", port=8001, health=True)
    
    # Test operations
    await registry.register(backend)
    backends = await registry.list_backends()
    print(f"Memory registry - Registered backends: {len(backends)}")
    
    await registry.unregister(backend)
    backends = await registry.list_backends()
    print(f"Memory registry - Remaining backends: {len(backends)}")


async def test_redis_registry():
    """Test the Redis registry."""
    print("\n=== Testing Redis Registry ===")
    
    try:
        # Create Redis registry
        registry = RegistryFactory.create_registry(registry_type="redis")
        
        # Create test backend
        backend = Backend(url="http://example.com", port=8002, health=True)
        
        # Test operations
        await registry.register(backend)
        backends = await registry.list_backends()
        print(f"Redis registry - Registered backends: {len(backends)}")
        
        await registry.unregister(backend)
        backends = await registry.list_backends()
        print(f"Redis registry - Remaining backends: {len(backends)}")
        
        # Close connection
        if hasattr(registry, 'close'):
            await registry.close()
            
    except Exception as e:
        print(f"Redis registry test failed: {e}")
        print("Make sure Redis is running: redis-server")


async def test_environment_based():
    """Test using environment variable configuration."""
    print("\n=== Testing Environment-Based Configuration ===")
    
    # Test with memory (default)
    os.environ["REGISTRY_TYPE"] = "memory"
    registry = RegistryFactory.create_registry()
    print(f"Environment registry (memory): {type(registry).__name__}")
    
    # Test with Redis
    os.environ["REGISTRY_TYPE"] = "redis"
    registry = RegistryFactory.create_registry()
    print(f"Environment registry (redis): {type(registry).__name__}")
    
    if hasattr(registry, 'close'):
        await registry.close()


async def main():
    """Run all tests."""
    await test_memory_registry()
    await test_redis_registry()
    await test_environment_based()
    print("\n=== Tests completed ===")


if __name__ == "__main__":
    asyncio.run(main())
