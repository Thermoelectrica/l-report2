"""Tests for local image service."""

import base64
from pathlib import Path

import pytest

from render.services.local_image_service import LocalImageService


@pytest.fixture
def image_service():
    """Create a local image service instance."""
    return LocalImageService()


@pytest.fixture
def temp_image_dir(tmp_path):
    """Create a temporary directory with test images."""
    # Create a simple 1x1 PNG image (smallest valid PNG)
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    png_file = tmp_path / "test.png"
    png_file.write_bytes(png_data)

    # Create a simple JPEG image
    jpg_data = base64.b64decode(
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k="
    )
    jpg_file = tmp_path / "test.jpg"
    jpg_file.write_bytes(jpg_data)

    return tmp_path


def test_get_image_data_uri_png(image_service, temp_image_dir):
    """Test converting PNG image to data URI."""
    result = image_service.get_image_data_uri("test.png", temp_image_dir)

    assert result is not None
    assert result.startswith("data:image/png;base64,")
    assert len(result) > 50  # Should have base64 data


def test_get_image_data_uri_jpeg(image_service, temp_image_dir):
    """Test converting JPEG image to data URI."""
    result = image_service.get_image_data_uri("test.jpg", temp_image_dir)

    assert result is not None
    assert result.startswith("data:image/jpeg;base64,")
    assert len(result) > 50


def test_get_image_data_uri_nonexistent(image_service, temp_image_dir):
    """Test handling of nonexistent image file."""
    result = image_service.get_image_data_uri("nonexistent.png", temp_image_dir)

    assert result is None


def test_get_image_data_uri_unsupported_format(image_service, temp_image_dir):
    """Test handling of unsupported image format."""
    # Create a file with unsupported extension
    unsupported_file = temp_image_dir / "test.xyz"
    unsupported_file.write_text("not an image")

    result = image_service.get_image_data_uri("test.xyz", temp_image_dir)

    assert result is None


def test_get_image_data_uri_empty_filename(image_service, temp_image_dir):
    """Test handling of empty filename."""
    result = image_service.get_image_data_uri("", temp_image_dir)

    assert result is None


def test_get_image_data_uri_none_filename(image_service, temp_image_dir):
    """Test handling of None filename."""
    result = image_service.get_image_data_uri(None, temp_image_dir)

    assert result is None


def test_supported_formats(image_service):
    """Test that all expected formats are supported."""
    expected_formats = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".bmp"}

    assert set(image_service.supported_formats.keys()) == expected_formats


def test_mime_types(image_service):
    """Test that MIME types are correctly mapped."""
    assert image_service.supported_formats[".png"] == "image/png"
    assert image_service.supported_formats[".jpg"] == "image/jpeg"
    assert image_service.supported_formats[".jpeg"] == "image/jpeg"
    assert image_service.supported_formats[".gif"] == "image/gif"
    assert image_service.supported_formats[".svg"] == "image/svg+xml"
    assert image_service.supported_formats[".webp"] == "image/webp"
    assert image_service.supported_formats[".bmp"] == "image/bmp"
