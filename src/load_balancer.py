from abc import ABC, abstractmethod
from typing import Optional


class LoadBalancer(ABC):
    """
    Abstract base class for load balancers. Implementations should support registering/unregistering
    any backend API service, and selecting the next backend for routing requests.
    """

    @abstractmethod
    def get_next_backend(self) -> Optional[str]:
        """
        Return the URL of the next backend to route a request to, or None if none available.
        """
        pass
