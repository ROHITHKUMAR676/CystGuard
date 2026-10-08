from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import uuid4

from app.config import get_settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    original_filename: str
    content_type: str | None
    size_bytes: int


class StorageBackend(Protocol):
    def store(self, source: BinaryIO, filename: str, content_type: str | None = None) -> StoredObject: ...

    def open(self, key: str) -> BinaryIO: ...

    def delete(self, key: str) -> None: ...


class LocalStorage:
    """Local development storage; callers receive opaque keys, never filesystem paths."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = (root or get_settings().storage_root).expanduser().resolve()

    def store(self, source: BinaryIO, filename: str, content_type: str | None = None) -> StoredObject:
        safe_name = Path(filename.replace("\\", "/")).name or "upload"
        suffix = Path(safe_name).suffix[:16]
        object_id = uuid4().hex
        key = f"{object_id[:2]}/{object_id}{suffix}"
        destination = self._root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        try:
            with destination.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    size += len(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        return StoredObject(key=key, original_filename=safe_name, content_type=content_type, size_bytes=size)

    def open(self, key: str) -> BinaryIO:
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root) or not candidate.is_file():
            raise FileNotFoundError("Stored object was not found")
        return candidate.open("rb")

    def delete(self, key: str) -> None:
        candidate = (self._root / key).resolve()
        if not candidate.is_relative_to(self._root):
            raise ValueError("Invalid storage key")
        candidate.unlink(missing_ok=True)


def get_storage() -> StorageBackend:
    return LocalStorage()
