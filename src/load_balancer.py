from typing import Set, Optional, List
from abc import ABC, abstractmethod

class LoadBalancer(ABC):
    """
    Abstract base class for load balancers. Implementations should support registering/unregistering
    any backend API service, and selecting the next backend for routing requests.
    """

    @abstractmethod
    def register(self, url: str, port: Optional[int] = None, **kwargs):
        """
        Register a backend service. Accepts URL, port, and optional metadata.
        """
        pass

    @abstractmethod
    def unregister(self, url: str, port: Optional[int] = None, **kwargs):
        """
        Unregister a backend service. Accepts URL, port, and optional metadata.
        """
        pass

    @abstractmethod
    def get_next_backend(self) -> Optional[str]:
        """
        Return the URL of the next backend to route a request to, or None if none available.
        """
        pass

    @abstractmethod
    def list_backends(self) -> List[dict]:
        """
        Return a list of all registered backends and their metadata.
        """
        pass