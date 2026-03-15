"""Abstract storage backend interface."""

from abc import ABC, abstractmethod
from uuid import UUID


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    async def save(self, render_id: UUID, pdf_bytes: bytes) -> str:
        """
        Save PDF and return storage path.

        Args:
            render_id: Unique render identifier
            pdf_bytes: PDF file content as bytes

        Returns:
            Storage path or URL where the file was saved
        """
        pass

    @abstractmethod
    async def retrieve(self, render_id: UUID) -> bytes:
        """
        Retrieve PDF bytes.

        Args:
            render_id: Unique render identifier

        Returns:
            PDF file content as bytes

        Raises:
            FileNotFoundError: If PDF does not exist
        """
        pass

    @abstractmethod
    async def exists(self, render_id: UUID) -> bool:
        """
        Check if PDF exists.

        Args:
            render_id: Unique render identifier

        Returns:
            True if PDF exists, False otherwise
        """
        pass

    @abstractmethod
    async def delete(self, render_id: UUID) -> None:
        """
        Delete PDF.

        Args:
            render_id: Unique render identifier
        """
        pass
