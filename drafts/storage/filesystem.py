"""Local filesystem storage backend."""

import logging
from pathlib import Path
from uuid import UUID

import aiofiles

from .base import StorageBackend

logger = logging.getLogger(__name__)


class FilesystemStorage(StorageBackend):
    """Store PDFs on local filesystem."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Filesystem storage initialized at: {self.base_path}")

    def _get_path(self, render_id: UUID) -> Path:
        """Get file path for a render ID."""
        return self.base_path / f"{render_id}.pdf"

    async def save(self, render_id: UUID, pdf_bytes: bytes) -> str:
        """Save PDF to filesystem."""
        path = self._get_path(render_id)
        async with aiofiles.open(path, "wb") as f:
            await f.write(pdf_bytes)
        logger.info(f"Saved PDF to: {path}")
        return str(path)

    async def retrieve(self, render_id: UUID) -> bytes:
        """Retrieve PDF from filesystem."""
        path = self._get_path(render_id)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {render_id}")
        async with aiofiles.open(path, "rb") as f:
            return await f.read()

    async def exists(self, render_id: UUID) -> bool:
        """Check if PDF exists on filesystem."""
        return self._get_path(render_id).exists()

    async def delete(self, render_id: UUID) -> None:
        """Delete PDF from filesystem."""
        path = self._get_path(render_id)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted PDF: {path}")
