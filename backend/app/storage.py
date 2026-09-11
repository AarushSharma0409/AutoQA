import uuid
from pathlib import Path
from typing import Protocol
from .config import settings


class Storage(Protocol):
    def put(self, content: bytes) -> str: ...
    def read(self, key: str) -> bytes: ...


class LocalStorage:
    def __init__(self, root: Path | None = None):
        self.root = (root or settings().storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key):
        if str(uuid.UUID(key)) != key:
            raise ValueError("Invalid storage key")
        return self.root / key

    def put(self, content):
        key = str(uuid.uuid4())
        self.path(key).write_bytes(content)
        return key

    def read(self, key):
        return self.path(key).read_bytes()


storage = LocalStorage()
