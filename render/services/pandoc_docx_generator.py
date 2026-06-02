"""Pandoc DOCX generator for Word document output."""

import logging
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile

from html2docx import html2docx # development
import mammoth # development
from html.parser import HTMLParser
from docx import Document # development
import pandoc # development
from .docx_generator import DocxGenerator # development

from .output_generator import OutputGenerator

from .docx_renderer import DocxRenderer # development

logger = logging.getLogger(__name__)

# Fixed filename for the reference DOCX file
REFERENCE_DOCX_FILENAME = "reference.docx"


class MyHTMLParser(HTMLParser): # development

    def __init__(self, doc):
        super().__init__()
        self.doc = doc

    def handle_data(self, data):
        self.doc.add_paragraph(data)


class PandocDocxGenerator(OutputGenerator):
    """Generate DOCX using Pandoc from HTML."""

    @property
    def format_name(self) -> str:
        return "pandoc-docx"

    @property
    def file_extension(self) -> str:
        return "docx"

    async def generate(
        self,
        #source_content: str,
        #source_path: Path,
        #base_url: str | None = None,
        **kwargs
    ) -> bytes:
        """
        Convert HTML to DOCX using Pandoc.

        Args:
            source_content: HTML string to convert
            source_path: Path to report folder (for accessing reference.docx)
            base_url: Base URL for resolving relative paths (not used for pandoc)

        Returns:
            DOCX file content as bytes
        """
        
        print(f"CALL DOCX RENDERER...")
        doc = DocxRenderer() # development
        return await doc.render(**kwargs) # development

# Global Pandoc DOCX generator instance
pandoc_docx_generator = PandocDocxGenerator()