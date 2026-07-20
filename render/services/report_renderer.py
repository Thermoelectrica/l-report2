"""Abstract base class for output generators."""

import importlib.util
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

from .local_image_service import local_image_service
from .repository import Report
from .s3_image_service import s3_image_service

logger = logging.getLogger(__name__)

JINJA_TEMPLATE_FILE = "index.html.j2"


class ReportRenderer(ABC):
    """Abstract base class for report renderers.

    Provides two concrete infrastructure methods shared by all renderers:

    ``build_context(report, parameters, query_results) -> dict``
        Assembles the standard template context and optionally delegates to
        ``transform_context(context)`` defined in the report's ``transform.py``.

    ``build_environment(report, **extra_filters) -> Environment``
        Creates a Jinja2 ``Environment`` configured for the report directory,
        registers generic filters, then optionally calls ``register_filters(env)``
        defined in the report's ``transform.py``.
        Pass additional filter callables as keyword arguments to inject
        renderer-specific filters (e.g. ``inline_image=<callable>``).
    """

    # ── Context builder ───────────────────────────────────────────────────────

    def build_context(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Build the template context for a report.

        Assembles the base context from report metadata, parameters and query
        results, then optionally delegates to ``transform_context(context)``
        defined in ``<report_dir>/transform.py``.

        Args:
            report: Report object with metadata and path.
            parameters: User-provided parameter values.
            query_results: Mapping of query name → list of row dicts.

        Returns:
            Final context dict ready to be passed to the template engine.
        """
        context: Dict[str, Any] = {
            "globals": {
                "template_name": report.id,
                "report_name": report.metadata.name,
                "generated_at": datetime.utcnow().isoformat(),
                "version": report.metadata.version,
            },
            "params": parameters,
            "queries": query_results,
        }

        module = self._load_transform_module(report)
        if module is not None and hasattr(module, "transform_context"):
            try:
                context = module.transform_context(context)
                logger.info(f"transform_context applied for report: {report.id}")
            except Exception as e:
                logger.error(
                    f"transform_context failed for {report.id}: {e}", exc_info=True
                )
                raise RuntimeError(
                    f"transform_context failed for report '{report.id}': {e}"
                )

        return context

    # ── Environment builder ───────────────────────────────────────────────────

    def build_environment(
        self,
        report: Report,
        **extra_filters: Any,
    ) -> Environment:
        """Create a Jinja2 Environment configured for *report*.

        Registers generic filters applicable to any report, then calls
        ``register_filters(env)`` from ``<report_dir>/transform.py`` if defined.

        Args:
            report: Report object — its ``path`` is used as the template loader
                    root and as the location of ``transform.py``.
            **extra_filters: Additional filter callables to register, keyed by
                filter name.  Useful for renderer-specific filters that require
                objects only available at render time (e.g. a ``DocxTemplate``
                instance for an ``inline_image`` filter).

        Returns:
            Configured Jinja2 ``Environment``.

        Raises:
            ValueError: If the report's template file does not exist.
            RuntimeError: If ``register_filters`` raises an exception.
        """
        template_file = Path(f"{report.path}/{JINJA_TEMPLATE_FILE}")
        if not template_file.exists():
            raise ValueError(
                f"Missing {JINJA_TEMPLATE_FILE} in {report.path}"
            )

        env = Environment(
            loader=FileSystemLoader(str(report.path)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # ── Generic filters (applicable to any report) ───────────────────────
        env.filters["format_number"] = (
            lambda x: f"{x:,.2f}" if x is not None else ""
        )
        env.filters["format_date"] = (
            lambda x: x.strftime("%d.%m.%Y") if x else ""
        )
        env.filters["format_datetime"] = (
            lambda x: x.strftime("%d.%m.%Y %H:%M") if x else ""
        )
        env.filters["image_url"] = s3_image_service.image_url
        env.filters["local_image"] = (
            lambda filename: local_image_service.get_image_data_uri(
                filename, report.path
            )
        )

        # ── Renderer-specific extra filters ──────────────────────────────────
        for name, fn in extra_filters.items():
            env.filters[name] = fn

        # ── Report-specific filters via transform.py hook ────────────────────
        module = self._load_transform_module(report)
        if module is not None and hasattr(module, "register_filters"):
            try:
                module.register_filters(env)
                logger.info(f"register_filters applied for report: {report.id}")
            except Exception as e:
                logger.error(
                    f"register_filters failed for {report.id}: {e}", exc_info=True
                )
                raise RuntimeError(
                    f"register_filters failed for report '{report.id}': {e}"
                )

        return env

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _load_transform_module(self, report: Report) -> Any:
        """Load and return the report's ``transform.py`` module, or ``None``."""
        transformer_path = report.path / "transform.py"
        if not transformer_path.exists():
            return None
        try:
            spec = importlib.util.spec_from_file_location(
                f"report_transform_{report.id}", transformer_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    f"Cannot load transform.py for report '{report.id}'"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            return module
        except Exception as e:
            logger.error(
                f"Failed to load transform.py for {report.id}: {e}", exc_info=True
            )
            raise RuntimeError(
                f"Failed to load transform.py for report '{report.id}': {e}"
            )

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    async def render(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> bytes:
        """Render the report and return the output as bytes."""
        pass

    @abstractmethod
    async def render_preview(
        self,
        report: Report,
        parameters: Dict[str, Any],
        query_results: Dict[str, List[Dict[str, Any]]],
    ) -> str | None:
        """Render an HTML preview. Returns None if the format has no preview."""
        pass

    @property
    @abstractmethod
    def supports_preview(self) -> bool:
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Format identifier used for registry lookup (e.g. ``"weasyprint"``)."""
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """File extension produced by this renderer (e.g. ``"pdf"``)."""
        pass
