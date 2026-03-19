"""Local filesystem storage backend."""

import logging
from pathlib import Path

import aiofiles

from .base import StorageBackend

logger = logging.getLogger(__name__)


class FilesystemStorage(StorageBackend):
    """Store output files on local filesystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Filesystem storage initialized at: {self.base_path}")

    def _get_path(self, cache_key: str, file_extension: str = "pdf") -> Path:
        """Get file path for a cache key."""
        return self.base_path / f"{cache_key}.{file_extension}"

    async def save(self, cache_key: str, pdf_bytes: bytes, file_extension: str = "pdf") -> str:
        """Save output file to filesystem."""
        path = self._get_path(cache_key, file_extension)
        async with aiofiles.open(path, "wb") as f:
            await f.write(pdf_bytes)
        logger.info(f"Saved file to: {path}")
        return str(path)

    async def retrieve(self, cache_key: str) -> bytes:
        """Retrieve file from filesystem (tries common extensions)."""
        # Try to find the file with any extension
        for ext in ["pdf", "docx", "html"]:
            path = self._get_path(cache_key, ext)
            if path.exists():
                async with aiofiles.open(path, "rb") as f:
                    return await f.read()
        raise FileNotFoundError(f"File not found: {cache_key}")

    async def exists(self, cache_key: str) -> bool:
        """Check if file exists on filesystem (tries common extensions)."""
        for ext in ["pdf", "docx", "html"]:
            if self._get_path(cache_key, ext).exists():
                return True
        return False

    async def delete(self, cache_key: str) -> None:
        """Delete file from filesystem (tries common extensions)."""
        for ext in ["pdf", "docx", "html"]:
            path = self._get_path(cache_key, ext)
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {path}")
