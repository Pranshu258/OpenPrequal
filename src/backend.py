from typing import Optional

class Backend:
    def __init__(self, url: str, port: Optional[int] = None, health: bool = False):
        self.url = url
        self.port = port
        self.health = health

    def __eq__(self, other):
        if not isinstance(other, Backend):
            return False
        return self.url == other.url and self.port == other.port

    def __hash__(self):
        return hash((self.url, self.port))

    def __repr__(self):
        return f"Backend(url={self.url}, port={self.port}, health={self.health})"
