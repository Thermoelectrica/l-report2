"""Storage backends for PDF files."""

from .base import StorageBackend
from .filesystem import FilesystemStorage
from .s3 import S3Storage
from ..config import settings


def get_storage() -> StorageBackend:
    """Get configured storage backend."""
    if settings.storage_backend == "s3":
        return S3Storage()
    else:
        return FilesystemStorage(settings.storage_path)


__all__ = ["StorageBackend", "FilesystemStorage", "S3Storage", "get_storage"]
