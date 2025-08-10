from typing import List

from contracts.backend import Backend


class BackendRegistry:
    def __init__(self):
        # Use a dict to ensure canonical Backend objects by (url, port)
        self._backends = {}

    async def register(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends[key] = backend
        # else: keep the existing object (preserve probe state)
        return {"status": "registered", "backend": self._backends[key].model_dump()}

    async def unregister(self, backend: Backend):
        key = (backend.url, backend.port)
        self._backends.pop(key, None)
        return {"status": "unregistered", "backend": backend.model_dump()}

    def list_backends(self) -> List[Backend]:
        return list(self._backends.values())
