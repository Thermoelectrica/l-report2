"""Jinja2 template renderer."""

import locale
import logging
from datetime import datetime
from typing import Any, Dict, List
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from .local_image_service import local_image_service
from .repository import Report
from .s3_image_service import s3_image_service

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Render Jinja2 templates with query results and parameters."""

    def __init__ (self):
        self.file_template = "index.html.j2"

    def _create_environment(self, report: Report) -> Environment:
        """Create Jinja2 environment for specific report."""

        template_file = Path(f"{report.path}/{self.file_template}")
        if not template_file.exists():
            raise ValueError(f"Missing {self.file_template} in {report.path}")
        
        env = Environment(
            loader=FileSystemLoader(str(report.path)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
        env.filters["format_number"] = lambda x: f"{x:,.2f}" if x is not None else ""
        env.filters["format_date"] = lambda x: x.strftime("«%d» %B %Y г.") if x else ""
        env.filters["format_datetime"] = lambda x: (
            x.strftime("«%d» %B %Y г. %H:%M") if x else ""
        )

        # Add S3 image URL filter
        env.filters["image_url"] = s3_image_service.image_url

        # Add local image filter (converts local images to base64 data URIs)
        env.filters["local_image"] = lambda filename: local_image_service.get_image_data_uri(
            filename, report.path
        )

        return env

    def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str:
        """
        Render template with context.

        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as list of dictionaries

        Returns:
            Rendered HTML string
        """
        try:
            env = self._create_environment(report)
            template = env.get_template(self.file_template)

            # Build context
            context = {
                "globals": {
                    "template_name": report.id,
                    "report_name": report.metadata.name,
                    "generated_at": datetime.utcnow().isoformat(),
                    "version": report.metadata.version,
                },
                "params": parameters,
                "queries": query_results,
            }

            logger.info(f"Rendering template for report: {report.id}")
            html = template.render(**context)
            logger.info(
                f"Template rendered successfully, HTML length: {len(html)} chars"
            )

            return html

        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            raise RuntimeError(f"Failed to render template: {e}")


# Global template renderer instance
template_renderer = TemplateRenderer()
