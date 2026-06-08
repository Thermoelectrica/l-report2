"""Abstract base class for output generators."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from .repository import Report


class ReportRenderer(ABC):
    """Абстрактный базовый класс для рендереров отчётов.
    Рендерер объединяет рендеринг jinja-шаблона и генерацию выходного файла
    в единую операцию. Разные реализации могут использовать разные
    шаблонизаторы и выходные форматы.
    """

    @abstractmethod
    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> bytes:
        """Отрендерить отчёт и вернуть байты результата."""
        pass

    @abstractmethod
    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Отрендерить HTML-превью. Возвращает None, если формат не поддерживает превью."""
        pass

    @property
    @abstractmethod
    def supports_preview(self) -> bool:
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
