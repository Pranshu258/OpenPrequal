import itertools
from typing import Set, Optional

class LoadBalancer:
    def __init__(self):
        self.registered_backends: Set[str] = set()
        self.backend_iter: Optional[itertools.cycle] = None

    def update_backend_iter(self):
        if self.registered_backends:
            self.backend_iter = itertools.cycle(list(self.registered_backends))
        else:
            self.backend_iter = None

    def register(self, url: str):
        self.registered_backends.add(url)
        self.update_backend_iter()

    def unregister(self, url: str):
        self.registered_backends.discard(url)
        self.update_backend_iter()

    def get_next_backend(self) -> Optional[str]:
        if not self.backend_iter:
            return None
        return next(self.backend_iter)

    def list_backends(self):
        return list(self.registered_backends)
