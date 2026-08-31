"""Local image service for embedding images from report directories."""

import base64
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LocalImageService:
    """Service for handling locally-stored images in report templates."""

    def __init__(self):
        """Initialize local image service."""
        self.supported_formats = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        logger.info("Local image service initialized")

    def get_image_data_uri(
        self, image_filename: str, report_path: Path
    ) -> Optional[str]:
        """
        Convert a local image file to a base64 data URI.

        Args:
            image_filename: Name of the image file (e.g., "logo.png")
            report_path: Path to the report directory containing the image

        Returns:
            Base64 data URI string (e.g., "data:image/png;base64,iVBORw0KG...")
            or None if the image cannot be loaded
        """
        if not image_filename:
            return None

        # Construct full path to image
        image_path = report_path / image_filename

        if not image_path.exists():
            logger.warning(f"Image file not found: {image_path}")
            return None

        if not image_path.is_file():
            logger.warning(f"Path is not a file: {image_path}")
            return None

        # Check if file extension is supported
        file_ext = image_path.suffix.lower()
        if file_ext not in self.supported_formats:
            logger.warning(
                f"Unsupported image format: {file_ext} for {image_filename}. "
                f"Supported formats: {', '.join(self.supported_formats.keys())}"
            )
            return None

        try:
            # Read image file as binary
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()

            # Encode to base64
            base64_data = base64.b64encode(image_data).decode("utf-8")

            # Get MIME type
            mime_type = self.supported_formats[file_ext]

            # Create data URI
            data_uri = f"data:{mime_type};base64,{base64_data}"

            logger.debug(
                f"Successfully encoded image: {image_filename} "
                f"({len(image_data)} bytes -> {len(data_uri)} chars)"
            )

            return data_uri

        except Exception as e:
            logger.error(f"Failed to encode image {image_filename}: {e}")
            return None


# Global local image service instance
local_image_service = LocalImageService()
