"""Abstract storage backend interface."""

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(self, cache_key: str, pdf_bytes: bytes) -> str:
        """
        Save PDF and return storage path.

        Args:
            cache_key: Unique cache key (parameter hash)
            pdf_bytes: PDF file content as bytes

        Returns:
            Storage path or URL where the file was saved
        """
        pass

    @abstractmethod
    async def retrieve(self, cache_key: str) -> bytes:
        """
        Retrieve PDF bytes.

        Args:
            cache_key: Unique cache key (parameter hash)

        Returns:
            PDF file content as bytes

        Raises:
            FileNotFoundError: If PDF does not exist
        """
        pass

    @abstractmethod
    async def exists(self, cache_key: str) -> bool:
        """
        Check if PDF exists.

        Args:
            cache_key: Unique cache key (parameter hash)

        Returns:
            True if PDF exists, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, cache_key: str) -> None:
        """
        Delete PDF.

        Args:
            cache_key: Unique cache key (parameter hash)
        """
        pass
