from abc import ABC, abstractmethod
from typing import List, Optional


class Registry(ABC):
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
    def list_backends(self) -> List[dict]:
        """
        Return a list of all registered backends and their metadata.
        """
        pass
