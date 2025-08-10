import importlib
from typing import List, Optional, Set

from src.backend import Backend


class BackendRegistry:
    def __init__(self):
        self.registered_backends: Set[Backend] = set()

    async def register(self, backend: Backend):
        self.registered_backends.add(backend)
        return {"status": "registered", "backend": backend.model_dump()}

    async def unregister(self, backend: Backend):
        self.registered_backends.discard(backend)
        return {"status": "unregistered", "backend": backend.model_dump()}

    def list_backends(self) -> List[Backend]:
        return [b for b in self.registered_backends]
