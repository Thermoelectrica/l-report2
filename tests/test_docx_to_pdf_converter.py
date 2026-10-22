"""Тесты для docx_to_pdf_converter."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from render.services.docx_to_pdf_converter import DocxToPdfConverter


class TestDocxToPdfConverter:
    """Тесты конвертера DOCX → PDF."""

    @pytest.fixture
    def converter(self):
        """Создаёт экземпляр конвертера с моковым LibreOffice."""
        return DocxToPdfConverter(libreoffice_path="/usr/bin/libreoffice")

    @pytest.mark.asyncio
    async def test_convert_success(self, converter, tmp_path):
        """Успешная конвертация DOCX → PDF."""
        # Создаём тестовый DOCX (просто байты)
        docx_bytes = b"fake docx content"

        # Мокаем subprocess.run для симуляции успешной конвертации
        mock_pdf_path = tmp_path / "input.pdf"
        mock_pdf_path.write_bytes(b"fake pdf content")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            # Мокаем glob для возврата PDF файла
            with patch.object(Path, "glob", return_value=[mock_pdf_path]):
                result = await converter.convert(docx_bytes)

        assert result == b"fake pdf content"
        mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_convert_failure(self, converter):
        """Конвертация не удалась (ошибка LibreOffice)."""
        docx_bytes = b"fake docx content"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Error: invalid argument",
                stdout=""
            )

            with pytest.raises(RuntimeError, match="LibreOffice conversion failed"):
                await converter.convert(docx_bytes)

    @pytest.mark.asyncio
    async def test_convert_timeout(self, converter):
        """Конвертация превысила таймаут."""
        docx_bytes = b"fake docx content"

        with patch("subprocess.run") as mock_run:
            import subprocess
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="libreoffice", timeout=120)

            with pytest.raises(RuntimeError, match="timed out"):
                await converter.convert(docx_bytes)

    @pytest.mark.asyncio
    async def test_convert_no_pdf_generated(self, converter, tmp_path):
        """LibreOffice не создал PDF файл."""
        docx_bytes = b"fake docx content"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            # Мокаем glob для возврата пустого списка
            with patch.object(Path, "glob", return_value=[]):
                with pytest.raises(RuntimeError, match="No PDF file generated"):
                    await converter.convert(docx_bytes)

    @pytest.mark.asyncio
    async def test_convert_libreoffice_not_found(self, converter):
        """LibreOffice не установлен."""
        docx_bytes = b"fake docx content"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            with pytest.raises(RuntimeError, match="LibreOffice not found"):
                await converter.convert(docx_bytes)

    def test_custom_libreoffice_path(self):
        """Использование пользовательского пути к LibreOffice."""
        converter = DocxToPdfConverter(libreoffice_path="/custom/path/to/libreoffice")
        assert converter.libreoffice_path == "/custom/path/to/libreoffice"

    def test_default_libreoffice_path(self):
        """Использование пути по умолчанию."""
        converter = DocxToPdfConverter()
        assert converter.libreoffice_path == "libreoffice"
