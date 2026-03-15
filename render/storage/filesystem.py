"""Local filesystem storage backend."""

import logging
from pathlib import Path

import aiofiles

from .base import StorageBackend

logger = logging.getLogger(__name__)


class FilesystemStorage(StorageBackend):
    """Store PDFs on local filesystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Filesystem storage initialized at: {self.base_path}")

    def _get_path(self, cache_key: str) -> Path:
        """Get file path for a cache key."""
        return self.base_path / f"{cache_key}.pdf"

    async def save(self, cache_key: str, pdf_bytes: bytes) -> str:
        """Save PDF to filesystem."""
        path = self._get_path(cache_key)
        async with aiofiles.open(path, "wb") as f:
            await f.write(pdf_bytes)
        logger.info(f"Saved PDF to: {path}")
        return str(path)

    async def retrieve(self, cache_key: str) -> bytes:
        """Retrieve PDF from filesystem."""
        path = self._get_path(cache_key)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {cache_key}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def exists(self, cache_key: str) -> bool:
        """Check if PDF exists on filesystem."""
        return self._get_path(cache_key).exists()

    async def delete(self, cache_key: str) -> None:
        """Delete PDF from filesystem."""
        path = self._get_path(cache_key)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted PDF: {path}")
