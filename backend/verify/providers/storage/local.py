from __future__ import annotations

from pathlib import Path

from verify.providers.base import BlobStore


class LocalBlobStore(BlobStore):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    async def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()
