"""
Registry factory for creating backend registry instances.
"""
import logging
from typing import Optional

from abstractions.registry import Registry
from config.config import Config
from core.backend_registry import BackendRegistry

logger = logging.getLogger(__name__)


class RegistryFactory:
    """
    Factory class for creating backend registry instances.
    """

    @staticmethod
    def create_registry(
        registry_type: Optional[str] = None,
        heartbeat_timeout: Optional[int] = None,
        **kwargs
    ) -> Registry:
        """
        Create a backend registry instance based on configuration.

        Args:
            registry_type (Optional[str]): Type of registry ("memory" or "redis").
                                         If None, uses Config.REGISTRY_TYPE.
            heartbeat_timeout (Optional[int]): Heartbeat timeout in seconds.
                                             If None, uses Config.HEARTBEAT_TIMEOUT.
            **kwargs: Additional keyword arguments for specific registry implementations.

        Returns:
            Registry: A registry instance.

        Raises:
            ValueError: If an unsupported registry type is specified.
            ImportError: If Redis dependencies are not available when redis type is requested.
        """
        registry_type = registry_type or Config.REGISTRY_TYPE
        heartbeat_timeout = heartbeat_timeout or Config.HEARTBEAT_TIMEOUT

        logger.info(f"Creating {registry_type} registry with heartbeat_timeout={heartbeat_timeout}")

        if registry_type.lower() == "memory":
            return BackendRegistry(heartbeat_timeout=heartbeat_timeout)
        
        elif registry_type.lower() == "redis":
            try:
                from core.redis_backend_registry import RedisBackendRegistry
                
                redis_url = kwargs.get("redis_url", Config.REDIS_URL)
                redis_db = kwargs.get("redis_db", Config.REDIS_DB)
                
                return RedisBackendRegistry(
                    redis_url=redis_url,
                    heartbeat_timeout=heartbeat_timeout,
                    db=redis_db,
                )
            except ImportError as e:
                logger.error(f"Redis dependencies not available: {e}")
                logger.warning("Falling back to memory registry")
                return BackendRegistry(heartbeat_timeout=heartbeat_timeout)
            except Exception as e:
                logger.error(f"Failed to create Redis registry: {e}")
                logger.warning("Falling back to memory registry")
                return BackendRegistry(heartbeat_timeout=heartbeat_timeout)
        
        else:
            supported_types = ["memory", "redis"]
            raise ValueError(
                f"Unsupported registry type: {registry_type}. "
                f"Supported types: {supported_types}"
            )


def get_default_registry() -> Registry:
    """
    Get the default registry instance based on current configuration.

    Returns:
        Registry: The default registry instance.
    """
    return RegistryFactory.create_registry()
