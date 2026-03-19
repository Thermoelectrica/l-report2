"""Tests for Pandoc DOCX generator."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from render.services.pandoc_docx_generator import (
    REFERENCE_DOCX_FILENAME,
    PandocDocxGenerator,
    pandoc_docx_generator,
)


class TestPandocDocxGenerator:
    """Test suite for PandocDocxGenerator."""

    def test_format_name(self):
        """Test format_name property returns correct value."""
        generator = PandocDocxGenerator()
        assert generator.format_name == "pandoc-docx"

    def test_file_extension(self):
        """Test file_extension property returns correct value."""
        generator = PandocDocxGenerator()
        assert generator.file_extension == "docx"

    @pytest.mark.asyncio
    async def test_generate_basic_html(self, sample_html: str, temp_dir: Path):
        """Test basic DOCX generation from HTML."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        # Generate DOCX
        result = await generator.generate(
            source_content=sample_html,
            source_path=source_path,
        )

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0
        # DOCX files start with PK (ZIP signature)
        assert result[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_generate_with_reference_docx(self, sample_html: str, temp_dir: Path):
        """Test DOCX generation with reference document."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        # Create a minimal reference DOCX file (just a placeholder for testing)
        reference_path = source_path / REFERENCE_DOCX_FILENAME
        # Create a minimal valid DOCX (ZIP with required structure)
        import zipfile
        with zipfile.ZipFile(reference_path, 'w') as docx:
            docx.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')

        # Mock subprocess to verify reference doc is used
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            # Create a fake output file
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b'PK\x03\x04'
                
                try:
                    await generator.generate(
                        source_content=sample_html,
                        source_path=source_path,
                    )
                except Exception:
                    # Expected since we're mocking
                    pass

            # Verify pandoc was called with reference doc
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert '--reference-doc' in call_args
            assert str(reference_path) in call_args

    @pytest.mark.asyncio
    async def test_generate_without_reference_docx(self, sample_html: str, temp_dir: Path):
        """Test DOCX generation without reference document."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        # Mock subprocess to verify reference doc is NOT used
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            # Create a fake output file
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = b'PK\x03\x04'
                
                try:
                    await generator.generate(
                        source_content=sample_html,
                        source_path=source_path,
                    )
                except Exception:
                    # Expected since we're mocking
                    pass

            # Verify pandoc was called without reference doc
            assert mock_run.called
            call_args = mock_run.call_args[0][0]
            assert '--reference-doc' not in call_args

    @pytest.mark.asyncio
    async def test_generate_pandoc_not_found(self, sample_html: str, temp_dir: Path):
        """Test error handling when pandoc is not installed."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        with patch('subprocess.run', side_effect=FileNotFoundError("pandoc not found")):
            with pytest.raises(RuntimeError, match="Pandoc not found"):
                await generator.generate(
                    source_content=sample_html,
                    source_path=source_path,
                )

    @pytest.mark.asyncio
    async def test_generate_pandoc_execution_error(self, sample_html: str, temp_dir: Path):
        """Test error handling when pandoc execution fails."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        error = subprocess.CalledProcessError(
            returncode=1,
            cmd=['pandoc'],
            stderr='Pandoc error: invalid input'
        )
        
        with patch('subprocess.run', side_effect=error):
            with pytest.raises(RuntimeError, match="Pandoc execution failed"):
                await generator.generate(
                    source_content=sample_html,
                    source_path=source_path,
                )

    @pytest.mark.asyncio
    async def test_generate_with_complex_html(self, temp_dir: Path):
        """Test DOCX generation with complex HTML content."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        complex_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Complex Report</title>
            <style>
                body { font-family: Arial, sans-serif; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ddd; padding: 8px; }
                th { background-color: #4CAF50; color: white; }
                .highlight { background-color: yellow; }
            </style>
        </head>
        <body>
            <h1>Complex Report</h1>
            <h2>Section 1</h2>
            <p>This is a <strong>bold</strong> and <em>italic</em> text.</p>
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
                <li>Item 3</li>
            </ul>
            <h2>Section 2</h2>
            <table>
                <thead>
                    <tr>
                        <th>Column 1</th>
                        <th>Column 2</th>
                        <th>Column 3</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Data 1</td>
                        <td>Data 2</td>
                        <td>Data 3</td>
                    </tr>
                    <tr>
                        <td class="highlight">Highlighted</td>
                        <td>Normal</td>
                        <td>Normal</td>
                    </tr>
                </tbody>
            </table>
            <h2>Section 3</h2>
            <ol>
                <li>First step</li>
                <li>Second step</li>
                <li>Third step</li>
            </ol>
        </body>
        </html>
        """

        # Generate DOCX
        result = await generator.generate(
            source_content=complex_html,
            source_path=source_path,
        )

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_generate_cleans_up_temp_files(self, sample_html: str, temp_dir: Path):
        """Test that temporary files are cleaned up after generation."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        with patch('tempfile.NamedTemporaryFile') as mock_temp:
            # Create mock temp files
            mock_input = MagicMock()
            mock_input.name = str(temp_dir / 'temp_input.html')
            mock_input.__enter__ = MagicMock(return_value=mock_input)
            mock_input.__exit__ = MagicMock(return_value=False)
            
            mock_output = MagicMock()
            mock_output.name = str(temp_dir / 'temp_output.docx')
            mock_output.__enter__ = MagicMock(return_value=mock_output)
            mock_output.__exit__ = MagicMock(return_value=False)
            
            mock_temp.side_effect = [mock_input, mock_output]
            
            # Mock subprocess
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
                
                # Mock file operations
                with patch('builtins.open', create=True) as mock_open:
                    mock_open.return_value.__enter__.return_value.read.return_value = b'PK\x03\x04'
                    
                    # Mock Path.unlink
                    with patch('pathlib.Path.unlink') as mock_unlink:
                        try:
                            await generator.generate(
                                source_content=sample_html,
                                source_path=source_path,
                            )
                        except Exception:
                            pass
                        
                        # Verify cleanup was attempted
                        assert mock_unlink.called

    def test_global_instance(self):
        """Test that global instance is properly created."""
        assert pandoc_docx_generator is not None
        assert isinstance(pandoc_docx_generator, PandocDocxGenerator)
        assert pandoc_docx_generator.format_name == "pandoc-docx"
        assert pandoc_docx_generator.file_extension == "docx"

    @pytest.mark.asyncio
    async def test_generate_with_base_url_ignored(self, sample_html: str, temp_dir: Path):
        """Test that base_url parameter is accepted but not used (for compatibility)."""
        generator = PandocDocxGenerator()
        source_path = temp_dir / "test-report"
        source_path.mkdir()

        # Generate DOCX with base_url (should be ignored)
        result = await generator.generate(
            source_content=sample_html,
            source_path=source_path,
            base_url="http://example.com",
        )

        # Verify result
        assert isinstance(result, bytes)
        assert len(result) > 0
        assert result[:2] == b"PK"

    @pytest.mark.asyncio
    async def test_reference_docx_filename_constant(self):
        """Test that reference DOCX filename constant is correct."""
        assert REFERENCE_DOCX_FILENAME == "reference.docx"
