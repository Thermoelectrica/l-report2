"""Unit tests for storage backends."""

from pathlib import Path

import pytest

from render.storage.filesystem import FilesystemStorage


class TestFilesystemStorage:
    """Tests for FilesystemStorage backend."""

    @pytest.mark.asyncio
    async def test_save_and_retrieve(
        self, temp_storage_dir: Path, sample_pdf_bytes: bytes
    ):
        """Test saving and retrieving a PDF."""
        storage = FilesystemStorage(str(temp_storage_dir))
        cache_key = "test123abc"

        # Save PDF
        path = await storage.save(cache_key, sample_pdf_bytes)
        assert path == str(temp_storage_dir / f"{cache_key}.pdf")

        # Retrieve PDF
        retrieved = await storage.retrieve(cache_key)
        assert retrieved == sample_pdf_bytes

    @pytest.mark.asyncio
    async def test_exists(self, temp_storage_dir: Path, sample_pdf_bytes: bytes):
        """Test checking if PDF exists."""
        storage = FilesystemStorage(str(temp_storage_dir))
        cache_key = "test456def"

        # Should not exist initially
        assert await storage.exists(cache_key) is False

        # Save PDF
        await storage.save(cache_key, sample_pdf_bytes)

        # Should exist now
        assert await storage.exists(cache_key) is True

    @pytest.mark.asyncio
    async def test_delete(self, temp_storage_dir: Path, sample_pdf_bytes: bytes):
        """Test deleting a PDF."""
        storage = FilesystemStorage(str(temp_storage_dir))
        cache_key = "test789ghi"

        # Save PDF
        await storage.save(cache_key, sample_pdf_bytes)
        assert await storage.exists(cache_key) is True

        # Delete PDF
        await storage.delete(cache_key)
        assert await storage.exists(cache_key) is False

    @pytest.mark.asyncio
    async def test_retrieve_nonexistent(self, temp_storage_dir: Path):
        """Test retrieving a PDF that doesn't exist."""
        storage = FilesystemStorage(str(temp_storage_dir))

        with pytest.raises(FileNotFoundError):
            await storage.retrieve("nonexistent")

    @pytest.mark.asyncio
    async def test_storage_directory_created(self, temp_dir: Path):
        """Test storage directory is created if it doesn't exist."""
        storage_path = temp_dir / "new_storage"
        assert not storage_path.exists()

        storage = FilesystemStorage(str(storage_path)) # noqa

        assert storage_path.exists()
        assert storage_path.is_dir()

    @pytest.mark.asyncio
    async def test_multiple_pdfs(self, temp_storage_dir: Path):
        """Test storing multiple PDFs."""
        storage = FilesystemStorage(str(temp_storage_dir))

        pdfs = {
            "key1": b"%PDF-1.4 content1",
            "key2": b"%PDF-1.4 content2",
            "key3": b"%PDF-1.4 content3",
        }

        # Save all PDFs
        for key, content in pdfs.items():
            await storage.save(key, content)

        # Verify all exist
        for key in pdfs.keys():
            assert await storage.exists(key) is True

        # Verify content
        for key, expected_content in pdfs.items():
            content = await storage.retrieve(key)
            assert content == expected_content
