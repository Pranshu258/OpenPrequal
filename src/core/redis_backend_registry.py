import asyncio
import json
import logging
import time
from typing import List, Optional

import aioredis
from redis.exceptions import RedisError

from abstractions.registry import Registry
from config.logging_config import setup_logging
from contracts.backend import Backend
from core.profiler import Profiler

setup_logging()
logger = logging.getLogger(__name__)


class RedisBackendRegistry(Registry):
    """
    Redis-based registry for managing backend service instances and their heartbeat status.
    """

    @Profiler.profile
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        heartbeat_timeout: Optional[int] = None,
        db: int = 0,
    ):
        """
        Initialize the RedisBackendRegistry.

        Args:
            redis_url (str): Redis connection URL.
            heartbeat_timeout (Optional[int]): Timeout in seconds for backend heartbeats.
            db (int): Redis database number to use.
        """
        self.redis_url = redis_url
        self.db = db
        self.heartbeat_timeout = heartbeat_timeout or 10
        self._redis: Optional[aioredis.Redis] = None
        self._connection_lock = asyncio.Lock()  # Only for connection management
        self._connection_healthy = False
        
        # Redis key prefixes
        self.backend_key_prefix = "backend:"
        self.heartbeat_key_prefix = "heartbeat:"
        
        logger.info(
            f"RedisBackendRegistry initialized with redis_url={self.redis_url}, "
            f"heartbeat_timeout={self.heartbeat_timeout}, db={self.db}"
        )

    async def _get_redis(self) -> aioredis.Redis:
        """
        Get Redis connection with fast path optimization.
        
        Returns:
            aioredis.Redis: Redis connection instance.
        """
        # Fast path: if connection exists and is healthy, return immediately
        if self._redis and self._connection_healthy:
            return self._redis
            
        # Slow path: create/recreate connection with double-check locking
        async with self._connection_lock:
            if self._redis and self._connection_healthy:
                return self._redis
                
            try:
                # Close existing connection if any
                if self._redis:
                    try:
                        await self._redis.close()
                    except:
                        pass  # Ignore close errors
                    
                self._redis = aioredis.from_url(
                    self.redis_url,
                    db=self.db,
                    decode_responses=True,
                    socket_connect_timeout=3,  # Reduced timeout
                    socket_timeout=3,
                    retry_on_timeout=True,
                    health_check_interval=30,
                )
                
                # Single ping to verify connection
                await self._redis.ping()
                self._connection_healthy = True
                logger.info(f"Redis connected: {self.redis_url}")
                
            except Exception as e:
                self._connection_healthy = False
                self._redis = None
                logger.error(f"Redis connection failed: {e}")
                raise
                
        return self._redis

    async def _execute_redis_operation(self, operation):
        """
        Execute Redis operation with minimal retry overhead.
        
        Args:
            operation: Async function that takes redis connection as parameter.
            
        Returns:
            Result of the operation.
        """
        try:
            redis = await self._get_redis()
            return await operation(redis)
        except (ConnectionError, RedisError):
            # Mark connection as unhealthy and retry once
            self._connection_healthy = False
            try:
                redis = await self._get_redis()
                return await operation(redis)
            except Exception as e:
                logger.error(f"Redis operation failed after retry: {e}")
                raise

    def _get_backend_key(self, backend: Backend) -> str:
        """
        Generate Redis key for backend storage.
        
        Args:
            backend (Backend): Backend instance.
            
        Returns:
            str: Redis key for the backend.
        """
        return f"{self.backend_key_prefix}{backend.url}:{backend.port}"

    def _get_heartbeat_key(self, backend: Backend) -> str:
        """
        Generate Redis key for heartbeat storage.
        
        Args:
            backend (Backend): Backend instance.
            
        Returns:
            str: Redis key for the heartbeat.
        """
        return f"{self.heartbeat_key_prefix}{backend.url}:{backend.port}"

    @Profiler.profile
    async def register(self, backend: Backend):
        """
        Register backend with optimized Redis transaction.
        """
        async def _register_operation(redis):
            backend_key = self._get_backend_key(backend)
            heartbeat_key = self._get_heartbeat_key(backend)
            current_time = time.time()
            
            # Optimized transaction with minimal operations
            async with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(backend_key)
                        
                        # Check existing backend in single operation
                        existing_data = await redis.get(backend_key)
                        if existing_data:
                            existing_backend = Backend.model_validate_json(existing_data)
                            # Preserve critical state only
                            backend.health = existing_backend.health
                            backend.in_flight_requests = existing_backend.in_flight_requests
                            backend.rif_avg_latency = existing_backend.rif_avg_latency
                            backend.overall_avg_latency = existing_backend.overall_avg_latency
                        
                        # Single atomic transaction
                        pipe.multi()
                        backend_json = backend.model_dump_json()  # Direct JSON string
                        pipe.set(backend_key, backend_json)
                        pipe.set(heartbeat_key, current_time)
                        await pipe.execute()
                        
                        return backend.model_dump()
                        
                    except aioredis.WatchError:
                        continue  # Quick retry without logging
        
        try:
            backend_data = await self._execute_redis_operation(_register_operation)
            logger.info(f"Registered: {backend.url}:{backend.port}")
            return {"status": "registered", "backend": backend_data}
            
        except Exception as e:
            logger.error(f"Registration failed for {backend.url}:{backend.port}: {e}")
            raise

    @Profiler.profile
    async def unregister(self, backend: Backend):
        """
        Unregister backend with optimized atomic deletion.
        """
        async def _unregister_operation(redis):
            backend_key = self._get_backend_key(backend)
            heartbeat_key = self._get_heartbeat_key(backend)
            
            # Get data and delete atomically
            async with redis.pipeline(transaction=True) as pipe:
                backend_data = await redis.get(backend_key)
                backend_obj = Backend.model_validate_json(backend_data) if backend_data else backend
                
                pipe.multi()
                pipe.delete(backend_key, heartbeat_key)  # Delete both keys in one command
                await pipe.execute()
                
                return backend_obj
        
        try:
            backend_obj = await self._execute_redis_operation(_unregister_operation)
            logger.info(f"Unregistered: {backend.url}:{backend.port}")
            return {"status": "unregistered", "backend": backend_obj.model_dump()}
            
        except Exception as e:
            logger.error(f"Unregistration failed for {backend.url}:{backend.port}: {e}")
            raise

    async def _get_all_backends_from_redis(self) -> List[Backend]:
        """
        Optimized batch retrieval of all backends.
        """
        async def _get_backends_operation(redis):
            # Single KEYS command
            backend_keys = await redis.keys(f"{self.backend_key_prefix}*")
            if not backend_keys:
                return []
            
            # Batch get all backend data
            async with redis.pipeline(transaction=False) as pipe:
                for key in backend_keys:
                    pipe.get(key)
                backend_data_list = await pipe.execute()
            
            # Fast parsing with error handling
            backends = []
            corrupted_keys = []
            
            for i, backend_data in enumerate(backend_data_list):
                if backend_data:
                    try:
                        backend = Backend.model_validate_json(backend_data)
                        backends.append(backend)
                    except Exception:
                        corrupted_keys.append(backend_keys[i])
            
            # Batch cleanup corrupted data if any
            if corrupted_keys:
                async with redis.pipeline(transaction=False) as pipe:
                    for key in corrupted_keys:
                        pipe.delete(key)
                    await pipe.execute()
                logger.warning(f"Cleaned {len(corrupted_keys)} corrupted backend entries")
            
            return backends
        
        return await self._execute_redis_operation(_get_backends_operation)

    @Profiler.profile
    async def list_backends(self) -> List[Backend]:
        """
        Optimized backend listing with batch heartbeat processing.
        """
        async def _list_backends_operation(redis):
            now = time.time()
            backends = await self._get_all_backends_from_redis()
            
            if not backends:
                return []
            
            # Batch get all heartbeats
            async with redis.pipeline(transaction=False) as pipe:
                for backend in backends:
                    pipe.get(self._get_heartbeat_key(backend))
                heartbeat_values = await pipe.execute()
            
            # Process health status efficiently
            health_updates = []
            for i, backend in enumerate(backends):
                last_heartbeat = heartbeat_values[i]
                should_be_unhealthy = False
                
                if last_heartbeat:
                    try:
                        if now - float(last_heartbeat) > self.heartbeat_timeout:
                            should_be_unhealthy = True
                    except ValueError:
                        should_be_unhealthy = True
                else:
                    should_be_unhealthy = True
                
                # Only update if health status changed
                if should_be_unhealthy and backend.health:
                    backend.health = False
                    health_updates.append(backend)
            
            # Batch update health status if needed
            if health_updates:
                async with redis.pipeline(transaction=False) as pipe:
                    for backend in health_updates:
                        pipe.set(self._get_backend_key(backend), backend.model_dump_json())
                    await pipe.execute()
                logger.info(f"Marked {len(health_updates)} backends as unhealthy")
            
            return backends
        
        return await self._execute_redis_operation(_list_backends_operation)

    async def update_backend_health(self, backend: Backend, health: bool):
        """
        Optimized health update with minimal operations.
        """
        async def _update_health_operation(redis):
            backend_key = self._get_backend_key(backend)
            
            async with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(backend_key)
                        backend_data = await redis.get(backend_key)
                        
                        if backend_data:
                            backend_obj = Backend.model_validate_json(backend_data)
                            if backend_obj.health != health:  # Only update if changed
                                backend_obj.health = health
                                pipe.multi()
                                pipe.set(backend_key, backend_obj.model_dump_json())
                                await pipe.execute()
                                return True
                            return False  # No update needed
                        return False
                        
                    except aioredis.WatchError:
                        continue
        
        try:
            updated = await self._execute_redis_operation(_update_health_operation)
            if updated:
                logger.info(f"Health updated: {backend.url}:{backend.port} -> {health}")
        except Exception as e:
            logger.error(f"Health update failed for {backend.url}:{backend.port}: {e}")
            raise

    async def update_backend_metrics(
        self,
        backend: Backend,
        in_flight_requests: Optional[float] = None,
        rif_avg_latency: Optional[float] = None,
        overall_avg_latency: Optional[float] = None,
    ):
        """
        Optimized metrics update with change detection.
        """
        async def _update_metrics_operation(redis):
            backend_key = self._get_backend_key(backend)
            
            async with redis.pipeline(transaction=True) as pipe:
                while True:
                    try:
                        await pipe.watch(backend_key)
                        backend_data = await redis.get(backend_key)
                        
                        if backend_data:
                            backend_obj = Backend.model_validate_json(backend_data)
                            
                            # Only update changed metrics
                            changed = False
                            if in_flight_requests is not None and backend_obj.in_flight_requests != in_flight_requests:
                                backend_obj.in_flight_requests = in_flight_requests
                                changed = True
                            if rif_avg_latency is not None and backend_obj.rif_avg_latency != rif_avg_latency:
                                backend_obj.rif_avg_latency = rif_avg_latency
                                changed = True
                            if overall_avg_latency is not None and backend_obj.overall_avg_latency != overall_avg_latency:
                                backend_obj.overall_avg_latency = overall_avg_latency
                                changed = True
                            
                            if changed:
                                pipe.multi()
                                pipe.set(backend_key, backend_obj.model_dump_json())
                                await pipe.execute()
                            
                            return changed
                        return False
                        
                    except aioredis.WatchError:
                        continue
        
        try:
            updated = await self._execute_redis_operation(_update_metrics_operation)
            if updated:
                logger.debug(f"Metrics updated: {backend.url}:{backend.port}")
        except Exception as e:
            logger.error(f"Metrics update failed for {backend.url}:{backend.port}: {e}")
            raise

    async def cleanup_expired_backends(self):
        """
        Optimized cleanup with minimal Redis round trips.
        """
        async def _cleanup_operation(redis):
            now = time.time()
            timeout_threshold = self.heartbeat_timeout * 2  # Grace period
            
            # Get all backend keys in one operation
            backend_keys = await redis.keys(f"{self.backend_key_prefix}*")
            if not backend_keys:
                return 0
            
            # Batch get backend data and heartbeats
            all_keys = []
            for backend_key in backend_keys:
                all_keys.append(backend_key)  # Backend data
                # Extract backend info from key to construct heartbeat key
                key_suffix = backend_key[len(self.backend_key_prefix):]
                all_keys.append(f"{self.heartbeat_key_prefix}{key_suffix}")  # Heartbeat
            
            async with redis.pipeline(transaction=False) as pipe:
                for key in all_keys:
                    pipe.get(key)
                all_values = await pipe.execute()
            
            # Process results efficiently
            expired_keys = []
            for i in range(0, len(all_values), 2):
                backend_data = all_values[i]
                heartbeat_data = all_values[i + 1]
                backend_key = all_keys[i]
                heartbeat_key = all_keys[i + 1]
                
                should_expire = False
                
                if not backend_data:
                    should_expire = True
                elif heartbeat_data:
                    try:
                        if now - float(heartbeat_data) > timeout_threshold:
                            should_expire = True
                    except ValueError:
                        should_expire = True
                else:
                    should_expire = True
                
                if should_expire:
                    expired_keys.extend([backend_key, heartbeat_key])
            
            # Batch delete expired keys
            if expired_keys:
                async with redis.pipeline(transaction=False) as pipe:
                    pipe.delete(*expired_keys)  # Delete all keys in one command
                    await pipe.execute()
                return len(expired_keys) // 2  # Each backend has 2 keys
            
            return 0
        
        try:
            cleaned_count = await self._execute_redis_operation(_cleanup_operation)
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} expired backends")
            return cleaned_count
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            raise

    async def close(self):
        """
        Close Redis connection with minimal overhead.
        """
        async with self._connection_lock:
            if self._redis:
                try:
                    await self._redis.close()
                except:
                    pass  # Ignore close errors
                finally:
                    self._redis = None
                    self._connection_healthy = False

    async def __aenter__(self):
        """Async context manager entry."""
        await self._get_redis()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
