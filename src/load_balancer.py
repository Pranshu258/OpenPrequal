from typing import Set, Optional, List
from abc import ABC, abstractmethod

class LoadBalancer(ABC):
    @abstractmethod
    def register(self, url: str):
        pass

    @abstractmethod
    def unregister(self, url: str):
        pass

    @abstractmethod
    def get_next_backend(self) -> Optional[str]:
        pass

    @abstractmethod
    def list_backends(self) -> List[str]:
        pass
