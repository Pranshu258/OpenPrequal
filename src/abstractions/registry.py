from abc import ABC, abstractmethod
from typing import List

from contracts.backend import Backend


class Registry(ABC):
    """
    Abstract base class for backend registry implementations.
    """

    @abstractmethod
    async def register(self, backend: Backend):
        """
        Register a backend service.

        Args:
            backend (Backend): The backend instance to register.

        Returns:
            dict: Registration status and backend data.
        """

    @abstractmethod
    async def unregister(self, backend: Backend):
        """
        Unregister a backend service.

        Args:
            backend (Backend): The backend instance to unregister.

        Returns:
            dict: Unregistration status and backend data.
        """

    @abstractmethod
    async def list_backends(self) -> List[Backend]:
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
