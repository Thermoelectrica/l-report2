"""PDF generator using WeasyPrint."""

import logging
from io import BytesIO

from weasyprint import HTML

logger = logging.getLogger(__name__)


class PDFGenerator:
    """Convert HTML to PDF using WeasyPrint."""

    async def generate(self, html: str, base_url: str | None = None) -> bytes:
        """
        Convert HTML to PDF.

        Args:
            html: HTML string to convert
            base_url: Base URL for resolving relative paths

        Returns:
            PDF file content as bytes
        """
        try:
            logger.info("Generating PDF from HTML")

            # Create PDF
            pdf_file = BytesIO()
            HTML(string=html, base_url=base_url).write_pdf(pdf_file)
            pdf_bytes = pdf_file.getvalue()

            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise RuntimeError(f"PDF generation failed: {e}")


# Global PDF generator instance
pdf_generator = PDFGenerator()
