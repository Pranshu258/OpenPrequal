import importlib
from typing import List, Optional, Set

from backend import Backend


class BackendRegistry:
    def __init__(self):
        self.registered_backends: Set[Backend] = set()

    def register(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.add(backend)

    def unregister(self, url: str, port: Optional[int] = None):
        backend = Backend(url, port)
        self.registered_backends.discard(backend)

    def list_backends(self) -> List[dict]:
        return [b for b in self.registered_backends]
