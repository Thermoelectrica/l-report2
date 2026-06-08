"""Registry for output format generators."""

import logging
from typing import Dict

from .report_renderer import ReportRenderer

logger = logging.getLogger(__name__)


class ReportRegistry:
    """Registry for output format generators."""

    def __init__(self):
        self._generators: Dict[str, ReportRenderer] = {}

    def register(self, generator: ReportRenderer) -> None:
        """
        Register a generator.

        Args:
            generator: ReportRenderer instance to register
        """
        format_name = generator.format_name
        if format_name in self._generators:
            logger.warning(f"Overwriting existing generator for format: {format_name}")

        self._generators[format_name] = generator
        logger.info(f"Registered generator for format: {format_name}")

    def get_generator(self, format_name: str) -> ReportRenderer:
        """
        Get generator for specified format.

        Args:
            format_name: Format identifier (e.g., "weasyprint", "docx")

        Returns:
            ReportRenderer instance

        Raises:
            ValueError: If format is not registered
        """
        if format_name not in self._generators:
            available = ", ".join(self._generators.keys())
            raise ValueError(
                f"Unknown format: {format_name}. Available formats: {available}"
            )

        return self._generators[format_name]

    def list_formats(self) -> list[str]:
        """List all registered format names."""
        return list(self._generators.keys())

    def is_registered(self, format_name: str) -> bool:
        """Check if a format is registered."""
        return format_name in self._generators


# Global registry instance
renderer_registry = ReportRegistry()

# Register default generators
from .weasyprint_renderer import weasyprint_renderer

renderer_registry.register(weasyprint_renderer)
