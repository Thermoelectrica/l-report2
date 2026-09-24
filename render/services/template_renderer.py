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
        result = self.to_nearest_ten(number)
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

    def to_nearest_ten(self, number: float) -> int:
        """Округляет число до ближайшей десятичной части."""
        return math.floor(number / 10) * 10

    def extract_item(self, lst, idx=0):
        """Извлекает элемент по индексу, возвращает 0 если нет."""
        if not lst or idx >= len(lst):
            return 0
        value = lst[idx]
        if value is None or not isinstance(value, str):
            return value if value is not None else 0
        return self.t_sticker_parser(value)

    def history_inspection_parser(self, row: Dict[str, Any]) -> str:
        """ 
        Сравнивает текущие показания температуры (тепловизор, термоиндикаторная наклейка,
        превышение над окружающей средой) с историческими данными по тому же узлу
        оборудования. Определяет, развивается ли дефект или устранён.
        """
        try:
            unit_names = row.get("history_unit_names", [])
            unit_name = row.get("unit_name")
            idx = unit_names.index(unit_name)
        except (ValueError, TypeError):
            raise ValueError(f"The unit '{row.get('unit_name')}' is not in the list.")

        past = (
            f"Осмотр {self.add_day_parser(row['history_unit_detected_at'][idx], 0)} "
            f"- регистрация дефекта."
        )

        if row.get("defect_status") == "RESOLVED":
            present  = (
                f"Осмотр {self.add_day_parser(row['started_at'], 0)} "
                f"- дефект устранен."
            )
            return (past + "\n\n" + present)

        history_t_observed = self.extract_item(row.get("history_t_observed"), idx)
        history_t_sticker = self.extract_item(row.get("history_t_stickers"), idx)
        history_t_excess = self.extract_item(row.get("history_t_excess"), idx)
        history_t_environment = self.extract_item(row.get("history_t_environment"), idx)
        history_t_max = max(history_t_sticker, history_t_observed)
        
        t_sticker = self.t_sticker_parser(row.get("t_sticker"))
        t_observed  = row.get("t_observed") or 0
        t_environment = row.get("t_environment") or 0
        t_excess = row.get("t_excess") or 0
        t_max = max(t_sticker, t_observed)

        cond_one = (
            history_t_observed and 
            history_t_sticker and
            t_sticker and
            t_observed
        )

        if cond_one and (t_max - history_t_max) > 10:
            result = self.to_nearest_ten(t_max - history_t_max)
            present = (
                f"Осмотр {self.add_day_parser(row['started_at'], 0)} "
                f"- развитие дефекта, рост абсолютного значения "
                f"допустимой температуры на {result} °С."
            )
            return (past + "\n\n" + present)

        cond_two = (
            not (history_t_observed and 
            t_observed) and
            history_t_sticker and
            t_sticker
        )
        if cond_two and (t_sticker - history_t_sticker) > 10:
            result = self.to_nearest_ten(t_sticker - history_t_sticker)
            present = (
                f"Осмотр {self.add_day_parser(row['started_at'], 0)} "
                f"- развитие дефекта, рост температуры "
                f"Ттин на {result} °С."
            )
            return (past + "\n\n" + present)

        history_delta_t = history_t_observed - history_t_environment - history_t_excess
        delta_t = t_observed - t_environment - t_excess
        cond_three = (
            history_t_observed and 
            history_t_environment and
            history_t_excess and
            t_observed and
            t_environment and
            t_excess
        )
        if cond_three and (delta_t - history_delta_t) > 10:
            result = self.to_nearest_ten(delta_t - history_delta_t)
            present = (
                f"Осмотр {self.add_day_parser(row['started_at'], 0)} "
                f"- развитие дефекта, рост температуры "
                f"Тпрев на {result} °С."
            )
            return (past + "\n\n" + present)

        present = (
            f"Осмотр {self.add_day_parser(row['started_at'], 0)} "
            f"- дефект не устранен."
        )
        return (past + "\n\n" + present)

    def inspector_major_parser(self, data: List[Dict[str, Any]]) -> Dict[str, str]:
        """ Преобразует список старших инспекторов в словарь «имя → должность».
        Убирает дубликаты по full_name_major (оставляется последнее вхождение),
        подставляет должность по умолчанию, если она не указана. """
        seen_major = {
            item["full_name_major"]: item.get("position_major") or "Инженер теплового контроля"
            for item in data if item.get("full_name_major")
        }
        return seen_major

    def inspector_minor_parser(self, data: List[Dict[str, Any]]) -> Dict[str, str]:
        """ Преобразует список младших инспекторов в словарь «имя → должность».
            Убирает дубликаты по full_names_minor (оставляется последнее вхождение),
            подставляет должность по умолчанию, если она не указана. """
        seen_minors = {}
        for item in data:
            for elem in item.get("full_names_minor") or []:
                seen_minors.update(
                    {
                        elem: item.get("positions_minor") or "Инженер теплового контроля"
                    }
                )
        return seen_minors

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
        env.filters["history_inspection_parser"] = self.history_inspection_parser
        env.filters["inspector_major_parser"] = self.inspector_major_parser
        env.filters["inspector_minor_parser"] = self.inspector_minor_parser
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
