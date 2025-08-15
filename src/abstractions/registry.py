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
