from abc import ABC, abstractmethod
from typing import List, Optional

from contracts.backend import Backend


class Registry(ABC):
    """
    Abstract base class for backend registry implementations.
    """

    @abstractmethod
    def register(self, url: str, port: Optional[int] = None, **kwargs):
        """
        Register a backend service.

        Args:
            url (str): The URL of the backend service.
            port (Optional[int]): The port of the backend service.
            **kwargs: Additional metadata for registration.

        Returns:
            None
        """

    @abstractmethod
    def unregister(self, url: str, port: Optional[int] = None, **kwargs):
        """
        Unregister a backend service.

        Args:
            url (str): The URL of the backend service.
            port (Optional[int]): The port of the backend service.
            **kwargs: Additional metadata for unregistration.

        Returns:
            None
        """

    @abstractmethod
    def list_backends(self) -> List[Backend]:
        """
        Return a list of all registered backends and their metadata.

        Returns:
            List[Backend]: List of registered backend objects.
        """

    @abstractmethod
    async def mark_backend_unhealthy(self, backend_url: str) -> bool:
        """
        Mark a specific backend as unhealthy by its URL.

        Args:
            backend_url (str): The URL of the backend to mark as unhealthy.

        Returns:
            bool: True if backend was found and marked unhealthy, False if not found.
        """

    @abstractmethod
    async def is_backend_healthy(self, backend_url: str) -> bool:
        """
        Check if a specific backend is healthy by its URL.

        Args:
            backend_url (str): The URL of the backend to check.

        Returns:
            bool: True if backend exists and is healthy, False otherwise.
        """
