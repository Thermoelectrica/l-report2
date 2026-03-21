"""PDF Report Generator - Reflex Web Application."""

import logging
import sys
from pathlib import Path

import reflex as rx

from render.config import settings
from report2.main_page import index
from report2.preview.preview_page import preview_page

logger = logging.getLogger(__name__)

# Validate storage configuration on startup
upload_dir = str(rx.get_upload_dir())
storage_path = settings.storage_path

if Path(storage_path).resolve() != Path(upload_dir).resolve():
    logger.error(
        f"CONFIGURATION ERROR: storage_path '{storage_path}' does not match "
        f"Reflex upload directory '{upload_dir}'. "
        f"Please set STORAGE_PATH={upload_dir} in your .env file."
    )
    sys.exit(1)

logger.info(f"Storage path validated: {storage_path} matches Reflex upload directory")

app = rx.App()
app.add_page(index)
app.add_page(preview_page, route="/preview")
