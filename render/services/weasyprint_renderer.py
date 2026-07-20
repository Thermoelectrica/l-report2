"""WeasyPrint generator for PDF output."""

import logging
from io import BytesIO
from typing import Any, Dict, List

from weasyprint import HTML

from .report_renderer import ReportRenderer, JINJA_TEMPLATE_FILE
from .repository import Report

logger = logging.getLogger(__name__)


class WeasyPrintRenderer(ReportRenderer):
    """Generate PDF using WeasyPrint from a Jinja2 HTML template."""

    @property
    def format_name(self) -> str:
        return "weasyprint"

    @property
    def file_extension(self) -> str:
        return "pdf"

    @property
    def supports_preview(self) -> bool:
        return True

    def _render_html(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """Build context, create Jinja2 env, render template to HTML string."""
        context = self.build_context(report, parameters, query_results)
        env = self.build_environment(report)
        template = env.get_template(JINJA_TEMPLATE_FILE)
        html = template.render(**context)
        logger.info(
            f"Template rendered for report: {report.id}, "
            f"HTML length: {len(html)} chars"
        )
        return html

    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Return the rendered HTML that would be converted to PDF."""
        return self._render_html(report, parameters, query_results)

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """Render the report to PDF bytes via WeasyPrint.

        Args:
            report: Report object with template and metadata.
            parameters: User-provided parameter values.
            query_results: Mapping of query name → list of row dicts.
            base_url: Base URL for resolving relative asset paths.
                      Defaults to the report directory as a ``file://`` URI.

        Returns:
            PDF file content as bytes.
        """
        source_content = self._render_html(report, parameters, query_results)

        try:
            logger.info(f"Generating PDF from HTML (source: {report.path})")

            if base_url is None:
                base_url = report.path.resolve().as_uri()

            pdf_file = BytesIO()
            HTML(string=source_content, base_url=base_url).write_pdf(pdf_file)
            pdf_bytes = pdf_file.getvalue()

            logger.info(f"PDF generated successfully, size: {len(pdf_bytes)} bytes")
            return pdf_bytes

        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            raise RuntimeError(f"PDF generation failed: {e}")


# Global WeasyPrint renderer instance
weasyprint_renderer = WeasyPrintRenderer()
