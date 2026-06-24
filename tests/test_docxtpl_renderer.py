# tests/test_docxtpl_renderer.py
import asyncio
import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

# Импортируем тестируемый класс
from render.services.docxtpl_renderer import DocxTplRenderer
from render.services.repository import Report


@pytest.fixture
def renderer():
    """Создаёт экземпляр DocxTplRenderer с временными путями."""
    r = DocxTplRenderer()
    r.resized_images_store = Path(tempfile.mkdtemp(prefix="test_resized_images_store_"))
    r.output_path = Path(tempfile.mktemp(suffix=".docx"))
    return r


@pytest.fixture
def mock_report():
    """Создаёт мок Report."""
    report = MagicMock(spec=Report)
    report.path = Path(tempfile.mkdtemp(prefix="test_report_path_"))
    return report


@pytest.fixture
def sample_query_results():
    """Пример данных для тестов."""
    return {
        "data": [
            {
                "visual_image_id": "image1.jpg",
                "full_equipment_name": "Motor>A",
                "defect_type_name": "Overheat",
                "unit_name": "Unit1",
                "is_sticker_present": True,
                "sticker_name": "ST-001",
                "t_sticker": 45.0,
                "t_max": 80.0,
                "is_test_ready": True,
                "t_observed": 65.0,
                "t_environment": 25.0,
                "t_similar_unit": 60.0,
                "nominal_current": 10.0,
                "measured_current": 11.5,
                "t_excess": 20.0,
                "load_factor_range": "100%",
                "t_observed_excess_50": 10.0,
                "t_observed_excess_100": 20.0,
                "t_over_max_excess": 25.0,
                "criticality": "CRITICAL",
                "is_panel": "MOTOR",
            },
        ],
        "inspection_summary": [
            {
                "facility_name": "Boiler House",
                "inspection_point": "Pump A",
            }
        ]
    }

@pytest.fixture
def item():
    """Создаёт мок item."""
    return {"name": "test_image.jpg", "url": "http://example.com/image.jpg"}

@pytest.fixture
def valid_image_bytes():
    # Создаём валидное PNG в памяти
    img = Image.new("RGB", (100, 100), color="red")
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# Вспомогательная функция для async context manager
def _make_async_context_manager(obj):
    class AsyncCM:
        def __init__(self, obj):
            self.obj = obj
        async def __aenter__(self):
            return self.obj
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    return AsyncCM(obj)

# Ассинхронный итератор для тестов
class AsyncIteratorWrapper:
    def __init__(self, obj):
        self._iter = iter(obj)
    def __aiter__(self):
        return self
    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


# =========================
# Тесты create_folder
# =========================

@pytest.mark.asyncio
async def test_create_folder_creates_directory(renderer, tmp_path):
    new_folder = tmp_path / "new_dir"
    renderer.create_folder(new_folder)
    assert new_folder.exists()
    assert new_folder.is_dir()


# =========================
# Тесты fetch_async_data (загрузка изображений)
# =========================

@pytest.mark.asyncio
async def test_fetch_async_data_downloads_new_image(renderer, tmp_path, item, valid_image_bytes):
    # Подготовка
    file_name = tmp_path / "test_image.jpg"
    renderer.resized_images_store = tmp_path

    # Создаём мок для client
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_bytes = MagicMock(
        return_value=AsyncIteratorWrapper([valid_image_bytes])
    )

    client = MagicMock()
    client.stream = MagicMock(
        side_effect=lambda *args, **kwargs: _make_async_context_manager(mock_response)
    )

    # Выполнение
    result = await renderer.fetch_async_data(client, item)

    # Проверки
    assert result == 1
    assert file_name.exists()
    client.stream.assert_called_once()

@pytest.mark.asyncio
async def test_fetch_async_data_downloads_broken_image(renderer, tmp_path, item):
    # Подготовка
    file_name = tmp_path / "test_image.jpg"
    renderer.resized_images_store = tmp_path

    # Создаём мок для client
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    # Битое изображение (не PNG/JPEG)
    mock_response.aiter_bytes = MagicMock(
        return_value=AsyncIteratorWrapper([b"not an image at all"])
    )

    client = MagicMock()
    client.stream = MagicMock(
        side_effect=lambda *args, **kwargs: _make_async_context_manager(mock_response)
    )

    # Выполнение
    result = await renderer.fetch_async_data(client, item)

    # Проверки
    assert isinstance(result, str) and "Error" in result
    # Файл должен быть удалён
    assert not file_name.exists()  

@pytest.mark.asyncio
async def test_fetch_async_data_uses_cached_image(renderer, tmp_path, item):
    # Подготовка
    file_name = tmp_path / "test_image.jpg"
    file_name.write_bytes(b"cached_content")
    renderer.resized_images_store = tmp_path

    client = AsyncMock()

    # Выполнение
    result = await renderer.fetch_async_data(client, item)

    # Проверки
    assert result == 0  # файл был в кэше
    client.stream.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_async_data_timeout_error(renderer, tmp_path, item):
    renderer.resized_images_store = tmp_path

    client = MagicMock()
    client.stream = MagicMock(
        side_effect=lambda *args, **kwargs: _make_async_context_manager()
    )
    client.stream.side_effect = asyncio.TimeoutError()

    # Выполнение и проверка исключения
    result = await renderer.fetch_async_data(client, item)
    assert isinstance(result, str) and result.startswith("Error: Timeout")


# =========================
# Тесты fetch_images
# =========================

@pytest.mark.asyncio
async def test_fetch_images_no_images(renderer, sample_query_results):
    sample_query_results["data"] = []
    with patch("render.services.docxtpl_renderer.s3_image_service") as mock_s3:
        await renderer.fetch_images(sample_query_results)
        mock_s3.image_url.assert_not_called()

@pytest.mark.asyncio
async def test_fetch_images_logs_stats(renderer, sample_query_results, caplog, valid_image_bytes):
    with caplog.at_level(logging.INFO):
        with patch("render.services.docxtpl_renderer.s3_image_service.image_url") as mock_url, \
             patch("render.services.docxtpl_renderer.httpx.AsyncClient") as mock_client:
            
            mock_url.return_value = "http://example.com/img.jpg"

            mock_client_instance = MagicMock()
            
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.aiter_bytes = MagicMock(
                return_value=AsyncIteratorWrapper([valid_image_bytes])
            )
            
            mock_client_instance.stream = MagicMock(
                side_effect=lambda *args, **kwargs: _make_async_context_manager(mock_response)
            )
            
            mock_client.return_value.__aenter__.return_value = mock_client_instance
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
            
            await renderer.fetch_images(sample_query_results)
           
            assert "Images downloaded: 1" in caplog.text
            assert "from cache: 0" in caplog.text
            assert "errors: 0" in caplog.text
            