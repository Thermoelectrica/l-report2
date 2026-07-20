"""DOCX_TPL generator for DOCX output."""

import asyncio
import io
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
import httpx

from .report_renderer import ReportRenderer
from .repository import Report
from .s3_image_service import s3_image_service

logger = logging.getLogger(__name__)


class DocxTplRenderer(ReportRenderer):
    """Generate DOCX using docxtpl.

    This renderer is generic: it discovers the DOCX template file by looking
    for the filename declared in ``metadata.yaml`` under the key
    ``docx_template`` (defaults to ``template.docx``), and the logo by the key
    ``logo`` (defaults to ``logo.png``).

    Report-specific context transformation and custom Jinja2 filters are
    delegated to the optional ``transform.py`` file in the report directory
    (see ``ReportRenderer.build_context()`` and ``ReportRenderer.build_environment()``).
    """

    # Default asset filenames — can be overridden via metadata.yaml
    DEFAULT_DOCX_TEMPLATE = "template.docx"
    DEFAULT_LOGO = "logo.png"

    def __init__(self):
        self.resized_images_store = Path("./resized_images_store")
        self.blank_image = "blank_image"
        self.prefix_name = {0: "visual", 1: "thermal"}

    @property
    def format_name(self) -> str:
        return "docxtpl"

    @property
    def file_extension(self) -> str:
        return "docx"

    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Return None — docxtpl format does not support HTML preview."""
        return None

    @property
    def supports_preview(self) -> bool:
        return False

    # ── Image helpers ────────────────────────────────────────────────────────

    def _cleanup_file(self, file_name: str) -> None:
        """Safely remove a file."""
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
                logger.info(f"Cleaned up partial/corrupted file: {file_name}")
            except OSError as e:
                logger.warning(f"Failed to remove file {file_name}: {e}")

    def create_blank_image(self, folder: Path) -> None:
        """Create two blank placeholder images in *folder*."""
        for idx, size in enumerate([(511, 680), (511, 380)]):
            image = Image.new("RGB", size, (255, 255, 255))
            dest = f"{folder}/{self.blank_image}_{self.prefix_name[idx]}.jpg"
            image.save(dest)
            logger.info(f"Created blank image: {dest}")

    def create_folder(self, folder: Path) -> None:
        """Create *folder* and populate it with blank placeholder images."""
        if os.path.exists(folder):
            return
        folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory for images: {folder.resolve()}")
        self.create_blank_image(folder.resolve())

    async def fetch_async_data(self, client: httpx.AsyncClient, item: Dict[str, str]) -> str | bool:
        """Download and resize a single image.  Returns True (downloaded),
        False (already cached) or an error string."""
        file_name = str(Path(self.resized_images_store) / item["name"])
        if os.path.isfile(file_name):
            return False

        try:
            async with client.stream(
                "GET",
                item["url"],
                timeout=httpx.Timeout(30.0, connect=10.0, read=20.0),
                follow_redirects=True,
            ) as response:
                response.raise_for_status()
                with open(file_name, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

                with Image.open(file_name) as img:
                    width, height = img.size
                    exif_data = img.getexif()

                    # Thermal camera images (FLIR E6xt 320×240, FLIR E95 640×480)
                    if height in [240, 480]:
                        new_width = 511
                        new_height = int(height * (new_width / width))
                        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        exif_data[270] = "thermal"
                        img.save(file_name, exif=exif_data)
                        return True

                    if width > height:
                        img = img.rotate(-90, expand=True)
                        width, height = img.size
                    img = img.resize((511, 680), Image.Resampling.LANCZOS)
                    exif_data[270] = "visual"
                    img.save(file_name, exif=exif_data)
                return True

        except httpx.TimeoutException:
            logger.error(f"Timeout downloading {item['url']}")
            self._cleanup_file(file_name)
            return f"Error: Timeout for {item['name']}"
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} for {item['url']}")
            self._cleanup_file(file_name)
            return f"Error: HTTP {e.response.status_code} for {item['name']}"
        except Exception as exc:
            logger.exception(f"Failed to download {item['url']}")
            self._cleanup_file(file_name)
            return f"Error: {type(exc).__name__}: {exc}"

    async def fetch_images(
        self,
        query_results: Dict[str, List[Dict[str, Any]]],
        data_key: str = "data",
    ) -> None:
        """Download all images referenced in *query_results[data_key]*.

        Args:
            query_results: Full query results dict.
            data_key: Key in *query_results* whose rows contain image IDs.
                      Defaults to ``"data"`` for backward compatibility; reports
                      should pass the correct key via ``transform_context``.
        """
        rows = query_results.get(data_key, [])
        urls_collection = []
        for row in rows:
            image_keys = [k for k in row.keys() if "image_id" in k]
            for image_key in image_keys:
                image_obj = row.get(image_key)
                if not image_obj:
                    continue
                if isinstance(image_obj, list):
                    for img in image_obj:
                        urls_collection.append(
                            {"name": img, "url": s3_image_service.image_url(img)}
                        )
                else:
                    urls_collection.append(
                        {"name": image_obj, "url": s3_image_service.image_url(image_obj)}
                    )

        if not urls_collection:
            return

        async with httpx.AsyncClient() as client:
            tasks = [self.fetch_async_data(client, item) for item in urls_collection]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            downloaded = sum(1 for r in results if r is True)
            cached = sum(1 for r in results if r is False)
            errors = [r for r in results if isinstance(r, BaseException)]
            logger.info(
                f"Images downloaded: {downloaded}, from cache: {cached}, errors: {len(errors)}"
            )
            if errors:
                logger.error(
                    "Failed to download images:\n" + "\n".join(str(e) for e in errors)
                )

    def _find_image_exif(self, image_name: str) -> str:
        """Return EXIF ImageDescription tag (270) value for *image_name*."""
        file_path = str(Path(self.resized_images_store) / image_name)
        if os.path.isfile(file_path):
            try:
                with Image.open(file_path) as img:
                    return img.getexif().get(270, "")
            except Exception as e:
                logger.warning(f"Failed to read EXIF for {file_path}: {e}")
        return ""

    # ── Core rendering ───────────────────────────────────────────────────────

    def _resolve_asset(self, report: Report, metadata_key: str, default: str) -> Path:
        """Return path to a report asset, using metadata override or default."""
        filename = getattr(report.metadata, metadata_key, None) or default
        return report.path / filename

    def render_docx(
        self,
        report: Report,
        context: Dict[str, Any],
    ) -> bytes:
        """Render the DOCX template with *context* and return raw bytes.

        The context is expected to be fully prepared (including any
        report-specific transformations) before this method is called.
        docxtpl-specific objects (``InlineImage``) are injected here.

        Args:
            report: Report object (used to locate the DOCX template and logo).
            context: Fully built template context dict.
        """
        docx_file = self._resolve_asset(report, "docx_template", self.DEFAULT_DOCX_TEMPLATE)
        if not docx_file.exists():
            raise ValueError(f"Missing DOCX template '{docx_file.name}' in {report.path}")

        try:
            doc = DocxTemplate(docx_file)

            # Inject logo if the asset exists
            logo_file = self._resolve_asset(report, "logo", self.DEFAULT_LOGO)
            if logo_file.exists():
                context["logo_image"] = InlineImage(
                    doc, image_descriptor=str(logo_file), width=Mm(40)
                )

            # Inject InlineImage objects for rows that carry image IDs
            data_key = context.get("_data_key", "data")
            rows = context.get("queries", {}).get(data_key, [])
            for row in rows:
                image_keys = [k for k in row.keys() if "image_id" in k]
                pictures = []
                for idx, image_key in enumerate(image_keys):
                    image_obj = row.get(image_key)
                    image_descriptor = (
                        f"{self.resized_images_store}/"
                        f"{self.blank_image}_{self.prefix_name[idx]}.jpg"
                    )
                    if isinstance(image_obj, list):
                        for img in image_obj:
                            if self._find_image_exif(img) == self.prefix_name[idx]:
                                image_descriptor = f"{self.resized_images_store}/{img}"
                                break
                    elif isinstance(image_obj, str):
                        if self._find_image_exif(image_obj) == self.prefix_name[idx]:
                            image_descriptor = f"{self.resized_images_store}/{image_obj}"
                    pictures.append(
                        InlineImage(doc, image_descriptor=image_descriptor, width=Mm(67))
                    )
                row["pictures"] = pictures

            jinja_env = self.build_environment(report)
            doc.render(context, jinja_env)

            file_stream = io.BytesIO()
            doc.save(file_stream)
            file_stream.seek(0)
        except Exception as exc:
            logger.error(f"DOCX rendering failed: {exc}")
            raise RuntimeError(f"DOCX rendering failed: {exc}")

        return file_stream.getvalue()

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """Render the report to DOCX bytes.

        Args:
            report: Report object with template and metadata.
            parameters: User-provided parameter values.
            query_results: Mapping of query name → list of row dicts.
            base_url: Unused; kept for interface compatibility.

        Returns:
            DOCX file content as bytes.
        """
        try:
            logger.info(f"Generating DOCX (source: {report.path})")

            # Build context (applies transform_context hook if present)
            context = self.build_context(report, parameters, query_results)

            # Ensure image store directory exists
            await asyncio.to_thread(self.create_folder, self.resized_images_store)

            # Download images referenced in query results
            data_key = context.get("_data_key", "data")
            await self.fetch_images(query_results, data_key=data_key)

            # Render DOCX in a thread (blocking I/O)
            docx_bytes = await asyncio.to_thread(self.render_docx, report, context)
            logger.info(f"DOCX generated successfully, size: {len(docx_bytes)} bytes")
            return docx_bytes

        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
            raise RuntimeError(f"DOCX generation failed: {e}")


# Global DocxTplRenderer instance
docxtpl_renderer = DocxTplRenderer()
