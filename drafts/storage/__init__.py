"""Storage backends."""

from config import settings
from .base import StorageBackend
from .filesystem import FilesystemStorage
from .s3 import S3Storage


def get_storage() -> StorageBackend:
    """Get configured storage backend."""
    if settings.storage_backend == "filesystem":
        return FilesystemStorage(settings.storage_path)
    elif settings.storage_backend == "s3":
        return S3Storage()
    else:
        raise ValueError(f"Unknown storage backend: {settings.storage_backend}")


# Global storage instance
storage = get_storage()
