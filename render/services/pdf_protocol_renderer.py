"""PDF generator for PDF output using DOCX_TPL + LibreOffice conversion."""

import logging
from typing import Any, Dict, List

from render.services.docxtpl_renderer import DocxTplRenderer
from .docx_to_pdf_converter import docx_to_pdf_converter

from .repository import Report

logger = logging.getLogger(__name__)


class PdfProtocolRenderer(DocxTplRenderer):
    """Generate PDF using DOCX_TPL + LibreOffice conversion."""

    @property
    def format_name(self) -> str:
        return "pdf-protocol"

    @property
    def file_extension(self) -> str:
        return "pdf"

    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
        base_url: str | None = None,
    ) -> bytes:
        """
        Генерирует PDF через DOCX_TPL + конвертацию.
        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as DataFrames
            base_url: Base URL for resolving relative paths
        Returns:
            PDF file content as bytes
        """
        # Вызываем родительский метод для получения DOCX
        docx_bytes = await super().render(
            report, parameters, query_results, base_url
        )
        logger.info(f"DOCX generated successfully, size: {len(docx_bytes)} bytes")
        
        # Конвертируем DOCX в PDF
        try:
            logger.info("Converting DOCX to PDF")
            pdf_bytes = await docx_to_pdf_converter.convert(docx_bytes)
            logger.info(f"Converted to PDF, size: {len(pdf_bytes)} bytes")
        except Exception as e:
            logger.error(f"Converting DOCX to PDF failed: {e}")
            raise RuntimeError(f"Converting DOCX to PDF failed: {e}")
        
        return pdf_bytes

# Global PdfProtocolRenderer instance
pdf_protocol_renderer = PdfProtocolRenderer()
