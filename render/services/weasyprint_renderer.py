"""WeasyPrint generator for PDF output."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

from weasyprint import HTML

from .report_renderer import ReportRenderer
from .repository import Report
from .template_renderer import TemplateRenderer, template_renderer

logger = logging.getLogger(__name__)


class WeasyPrintRenderer(ReportRenderer):
    """Generate PDF using WeasyPrint from HTML."""

    def __init__(self, template_renderer: TemplateRenderer = template_renderer):
        self.template_renderer = template_renderer

    @property
    def format_name(self) -> str:
        return "weasyprint"

    @property
    def file_extension(self) -> str:
        return "pdf"

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> bytes:
        """Отрендерить отчёт и вернуть байты результата."""
        return self.template_renderer.render(report, parameters, query_results)

    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Отрендерить HTML-превью. Возвращает None, если формат не поддерживает превью."""
        return await self.render(report, parameters, query_results)

    @property
    def supports_preview(self) -> bool:
        pass

    async def generate(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """
        Takes Args and make PDF using WeasyPrint.
        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as DataFrames
            base_url: Base URL for resolving relative paths
        Returns:
            PDF file content as bytes
        """
        source_content = await self.render(report, parameters, query_results)

        try:
            logger.info(f"Generating PDF from HTML (source: {report.path})")

            # If base_url not provided, use report.path as base
            if base_url is None:
                # Convert to absolute path first to avoid "relative paths can't be expressed as file URIs" error
                absolute_path = report.path.resolve()
                base_url = absolute_path.as_uri()

            pdf_file = BytesIO()
            HTML(
                string=source_content, 
                base_url=base_url,
            ).write_pdf(pdf_file)
            pdf_bytes = pdf_file.getvalue()

            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise RuntimeError(f"PDF generation failed: {e}")


# Global WeasyPrint generator instance
weasyprint_renderer = WeasyPrintRenderer()