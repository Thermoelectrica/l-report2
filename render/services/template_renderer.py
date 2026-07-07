"""Jinja2 template renderer."""

import locale
import logging
import math
from datetime import datetime, timedelta
import re
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

    def add_day_parser(self, date_obj: datetime, day: int) -> str:
        """ Добавляет дни к дате и возвращает форматированную строку. """
        tomorrow = date_obj + timedelta(days=day)
        return tomorrow.strftime('«%d» %B %Y г.')
        
    def equipment_parser(self, name: str) -> str:
        """ Исправляет имя оборудования. """
        if not isinstance(name, str):
            return ""
        if ("Щит" in name):
            name = name.replace("Щит", "РУ -")
        if ("Ячейка КРУ" in name):
            name = name.replace("Ячейка КРУ", "КРУ -")
        if ("Электродвигатель" in name):
            name = name.replace("Электродвигатель", "Электродвигатели")
        return name

    def t_sticker_parser(self, sticker: str) -> int:
        """ Извлекает префикс стикера до первого дефиса. """
        if not isinstance(sticker, str):
            return 0
        try:
            value = re.search(r'\d+', sticker).group()
        except AttributeError:
            return 0
        return int(value)
    
    def inspection_summary_parser(
            self, 
            inspect_summary: List[Dict[str, Any]]
        ) -> Dict[str, List[Dict[str, Any]]]:
        """ Группирует список инспекционных точек по названию объекта (facility_name). """
        inspection_summary = {}
        for item in inspect_summary:
            key = item["facility_name"]
            if key in inspection_summary:
                inspection_summary[key].append(item)
            else:
                inspection_summary[key] = [item]
        return inspection_summary
    
    def output_parser(self, number: float) -> str:
        """Формирует строку-условие для превышения температуры, округляя значение до ближайших 10°C."""
        result = math.floor(number / 10) * 10
        if result >= 200:
            result = 200
        cond_string = f" более чем на {result} °C"
        if result == 0:
            cond_string = ""
        return cond_string

    def full_equipment_name_parser(self, equipment: str) -> str:
        """" Преобразует имя оборудования, заменяя символы ">" на перенос строки "\n". """
        if not isinstance(equipment, str):
            raise TypeError(f"Expected str, got {type(equipment).__name__}")
        return equipment.replace(">", "\n")
    
    def sticker_name_parser(self, sticker: str) -> str:
        """" Добавляет пробел перед °С. """
        if not isinstance(sticker, str):
            raise TypeError(f"Expected str, got {type(sticker).__name__}")
        return sticker.replace("°С", " °С")

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
        env.filters["t_sticker_parser"] = self.t_sticker_parser
        env.filters["inspection_summary_parser"] = self.inspection_summary_parser
        env.filters["full_equipment_name_parser"] = self.full_equipment_name_parser
        env.filters["sticker_name_parser"] = self.sticker_name_parser
        env.filters["output_parser"] = self.output_parser
        env.filters["equipment_parser"] = self.equipment_parser
        env.filters["add_day_parser"] = lambda dt, days=1: self.add_day_parser(dt, days)

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
