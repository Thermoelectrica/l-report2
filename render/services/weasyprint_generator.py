"""WeasyPrint generator for PDF output."""

import logging
from io import BytesIO
from pathlib import Path

from weasyprint import HTML

from .output_generator import OutputGenerator

logger = logging.getLogger(__name__)


class WeasyPrintGenerator(OutputGenerator):
    """Generate PDF using WeasyPrint from HTML."""

    @property
    def format_name(self) -> str:
        return "weasyprint"

    @property
    def file_extension(self) -> str:
        return "pdf"

    async def generate(
        self,
        source_content: str,
        source_path: Path,
        base_url: str | None = None,
    ) -> bytes:
        """
        Convert HTML to PDF using WeasyPrint.

        Args:
            source_content: HTML string to convert
            source_path: Path to report folder (for accessing images, etc.)
            base_url: Base URL for resolving relative paths

        Returns:
            PDF file content as bytes
        """
        try:
            logger.info(f"Generating PDF from HTML (source: {source_path})")

            # If base_url not provided, use source_path as base
            if base_url is None:
                # Convert to absolute path first to avoid "relative paths can't be expressed as file URIs" error
                absolute_path = source_path.resolve()
                base_url = absolute_path.as_uri()

            pdf_file = BytesIO()
            HTML(string=source_content, base_url=base_url).write_pdf(pdf_file)
            pdf_bytes = pdf_file.getvalue()

            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise RuntimeError(f"PDF generation failed: {e}")


# Global WeasyPrint generator instance
weasyprint_generator = WeasyPrintGenerator()
