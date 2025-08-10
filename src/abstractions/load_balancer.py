from abc import ABC, abstractmethod
from typing import Optional


class LoadBalancer(ABC):
    """
    Abstract base class for load balancers. Implementations should support selecting
    the next backend for routing requests.
    """

    @abstractmethod
    def get_next_backend(self) -> Optional[str]:
        """
        Return the URL of the next backend to route a request to, or None if none available.

        Returns:
            Optional[str]: The URL of the selected backend, or None if no backend is available.
        """
        pass
