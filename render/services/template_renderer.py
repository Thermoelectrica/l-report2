"""Jinja2 template renderer."""

import logging
from datetime import datetime
from typing import Any, Dict

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from .repository import Report
from .s3_image_service import s3_image_service

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Render Jinja2 templates with query results and parameters."""

    def _create_environment(self, report: Report) -> Environment:
        """Create Jinja2 environment for specific report."""
        env = Environment(
            loader=FileSystemLoader(str(report.path)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Add custom filters
        env.filters["format_number"] = lambda x: f"{x:,.2f}" if x is not None else ""
        env.filters["format_date"] = lambda x: x.strftime("%Y-%m-%d") if x else ""
        env.filters["format_datetime"] = lambda x: (
            x.strftime("%Y-%m-%d %H:%M:%S") if x else ""
        )

        # Add S3 image URL filter
        env.filters["image_url"] = s3_image_service.image_url

        return env

    def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, pd.DataFrame],
    ) -> str:
        """
        Render template with context.

        Args:
            report: Report object with template
            parameters: User-provided parameters
            query_results: Query results as DataFrames

        Returns:
            Rendered HTML string
        """
        try:
            env = self._create_environment(report)
            template = env.get_template("index.html.j2")

            # Build context
            context = {
                "globals": {
                    "template_name": report.id,
                    "report_name": report.metadata.name,
                    "generated_at": datetime.utcnow().isoformat(),
                    "version": report.metadata.version,
                },
                "params": parameters,
                "queries": {
                    name: df.to_dict("records") for name, df in query_results.items()
                },
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
