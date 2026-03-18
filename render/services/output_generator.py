"""Abstract base class for output generators."""

from abc import ABC, abstractmethod
from pathlib import Path


class OutputGenerator(ABC):
    """Abstract base class for output generators."""

    @abstractmethod
    async def generate(
        self,
        source_content: str,
        source_path: Path,
        base_url: str | None = None,
    ) -> bytes:
        """
        Generate output from source content.

        Args:
            source_content: Rendered template content
            source_path: Path to report folder for accessing additional files
            base_url: Optional base URL for resolving relative paths

        Returns:
            output_bytes
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """
        Return the format name this generator implements.
        This method should return specific name (weasyprint), not output extension.
        """
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Return the extension of the file this generator produces."""
        pass
