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
        source_content: str,
        source_path: Path,
        base_url: str | None = None,
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
        try:
            logger.info(f"Generating DOCX from HTML (source: {source_path})")
            print(f"Generating DOCX from HTML (source: {source_path})") # development

            # Check for reference DOCX file in source_path
            reference_docx_path = source_path / REFERENCE_DOCX_FILENAME
            print(f"REFERENCE_DOCX_FILENAME: {reference_docx_path}") # development
            reference_docx_exists = reference_docx_path.exists()

            if reference_docx_exists:
                logger.info(f"Found reference DOCX file: {reference_docx_path}")
            else:
                logger.info(f"No reference DOCX file found at {reference_docx_path}, using default pandoc styling")

            # Create temporary files for input and output
            with NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as input_file:
                input_file.write(source_content)
                input_file_path = input_file.name

            with NamedTemporaryFile(mode='rb', suffix='.docx', delete=False) as output_file:
                output_file_path = output_file.name

            print(f"INPUT FILE PATH: {input_file_path}") # development
            '''
            with open(input_file_path) as fp:
                html = fp.read()
            
            # html2docx() returns an io.BytesIO() object. The HTML must be valid.
            buf = html2docx(html, title="My Document")

            with open("my.docx", "wb") as fp:
                fp.write(buf.getvalue())
            
            with open("output2.docx", "wb") as docx_file:
                result = mammoth.convert_to_docx(html)
                docx_file.write(result.value)
            
         
            document = Document()
            parser = MyHTMLParser(document)
            parser.feed(html)
            document.save('output.docx')
            '''
            document = DocxGenerator()
            await document.generate_docx()  # development

            try:
                # Build pandoc command
                cmd = [
                    'pandoc1',
                    input_file_path,
                    '-f', 'html',
                    '-t', 'docx',
                    '-o', output_file_path,
                ]

                # Add reference document if it exists
                if reference_docx_exists:
                    cmd.extend(['--reference-doc', str(reference_docx_path)])

                # Execute pandoc
                logger.debug(f"Running pandoc command: {' '.join(cmd)}")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Read the generated DOCX file
                with open(output_file_path, 'rb') as f:
                    docx_bytes = f.read()

                logger.info(f"DOCX generated successfully, size: {len(docx_bytes)} bytes")
                return docx_bytes

            finally:
                # Clean up temporary files
                Path(input_file_path).unlink(missing_ok=True)
                Path(output_file_path).unlink(missing_ok=True)

        except subprocess.CalledProcessError as e:
            logger.error(f"Pandoc execution failed: {e.stderr}")
            raise RuntimeError(f"Pandoc execution failed: {e.stderr}")
        except FileNotFoundError:
            logger.error("Pandoc not found. Please install pandoc.")
            raise RuntimeError("Pandoc not found. Please install pandoc on your system.")
        except Exception as e:
            logger.error(f"DOCX generation failed: {e}")
            raise RuntimeError(f"DOCX generation failed: {e}")


# Global Pandoc DOCX generator instance
pandoc_docx_generator = PandocDocxGenerator()
