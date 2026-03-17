"""Main render service implementation."""

import asyncio
import hashlib
import json
import logging
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import and_, select

from ..database import AsyncSessionLocal
from ..database.models import Render
from ..models import (
    RenderResult,
    RenderStatus,
    ReportListItem,
    ReportMetadata,
    ReportParameter,
)
from ..storage import get_storage
from .interface import RenderService as RenderServiceInterface
from .pdf_generator import pdf_generator
from .query_executor import query_executor
from .repository import repository
from .template_renderer import template_renderer

logger = logging.getLogger(__name__)


class RenderServiceImpl(RenderServiceInterface):
    """Implementation of RenderService interface."""

    def __init__(self, cache_ttl_minutes: int = 5):
        """
        Initialize render service.

        Args:
            cache_ttl_minutes: Default cache time-to-live in minutes
        """
        self.cache_ttl_minutes = cache_ttl_minutes
        self.storage = get_storage()

    def _calculate_hash(self, report_id: str, parameters: Dict[str, Any]) -> str:
        """
        Calculate SHA256 hash of report_id and parameters.

        Args:
            report_id: Report template ID
            parameters: User-provided parameters

        Returns:
            Hex string of SHA256 hash
        """
        # Create a deterministic string representation
        data = {"report_id": report_id, "parameters": parameters}
        # Sort keys to ensure consistent hash
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    def listReports(self) -> List[ReportListItem]:
        """Get list of all available reports."""
        return repository.list_reports()

    async def getReportMetadata(self, report_id: str) -> ReportMetadata:
        """Get detailed metadata for a specific report with resolved dynamic enums."""
        # Get base metadata from repository
        metadata = repository.get_metadata(report_id)
        report = repository.get_report(report_id)

        # Create a deep copy to avoid modifying the cached metadata
        metadata_copy = deepcopy(metadata)

        # Resolve dynamic enums only if query executor is initialized
        if query_executor.pool is None:
            logger.warning(
                "Query executor not initialized. Dynamic enums will not be resolved. "
                "Call query_executor.initialize() first."
            )
            return metadata_copy

        logger.info(f"Resolving dynamic enums for report: {report_id}")

        # Resolve dynamic enums
        for param in metadata_copy.parameters:
            if param.enum_query:
                logger.info(
                    f"Found enum_query '{param.enum_query}' for parameter '{param.name}'"
                )
                # Find the query file
                query_file = report.path / param.enum_query

                if not query_file.exists():
                    logger.warning(
                        f"Enum query file not found: {param.enum_query} for parameter {param.name} "
                        f"(looked in {query_file})"
                    )
                    continue

                try:
                    # Execute the enum query
                    logger.info(f"Executing enum query from {query_file}")
                    enum_values = await query_executor.execute_enum_query(query_file)
                    param.enum = enum_values
                    logger.info(
                        f"Resolved {len(enum_values)} enum values for parameter {param.name}: {enum_values[:5]}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to execute enum query for parameter {param.name}: {e}",
                        exc_info=True,
                    )
                    # Keep the parameter without enum values

        return metadata_copy

    async def getRenderStatus(
        self, report_id: str, params: Dict[str, Any]
    ) -> RenderResult:
        """Get the current status and result of a report rendering."""
        # Calculate cache key
        cache_key = self._calculate_hash(report_id, params)

        # Get report metadata to check for per-report cache TTL
        metadata = repository.get_metadata(report_id)
        cache_ttl_minutes = metadata.cache_ttl_minutes or self.cache_ttl_minutes

        async with AsyncSessionLocal() as db:
            # Look up render record
            result = await db.execute(
                select(Render).where(Render.parameter_hash == cache_key)
            )
            render = result.scalar_one_or_none()

            if not render:
                # No render started yet
                return RenderResult(status=RenderStatus.PENDING)

            # Check if completed and not expired
            if render.status == RenderStatus.COMPLETED.value:
                cutoff_time = datetime.utcnow() - timedelta(minutes=cache_ttl_minutes)

                if render.completed_at and render.completed_at >= cutoff_time:
                    # Valid cached result - retrieve PDF
                    try:
                        pdf_bytes = await self.storage.retrieve(cache_key)
                        return RenderResult(
                            status=RenderStatus.COMPLETED, pdf_bytes=pdf_bytes
                        )
                    except FileNotFoundError:
                        logger.warning(
                            f"PDF file not found for cache key {cache_key[:8]}"
                        )
                        # Mark as pending to trigger re-render
                        return RenderResult(status=RenderStatus.PENDING)
                else:
                    # Expired cache
                    logger.info(f"Cache expired for {cache_key[:8]} (TTL: {cache_ttl_minutes} minutes)")
                    return RenderResult(status=RenderStatus.PENDING)

            elif render.status == RenderStatus.FAILED.value:
                return RenderResult(
                    status=RenderStatus.FAILED, error_message=render.error_message
                )

            elif render.status == RenderStatus.RUNNING.value:
                return RenderResult(status=RenderStatus.RUNNING)

            else:  # PENDING
                return RenderResult(status=RenderStatus.PENDING)

    async def executeRender(
        self, report_id: str, params: Dict[str, Any], force_refresh: bool = False
    ) -> RenderResult:
        """
        Execute complete render workflow and return the result.

        Args:
            report_id: Report template ID
            params: User-provided parameters
            force_refresh: Whether to bypass cache

        Returns:
            RenderResult with status COMPLETED or FAILED
        """
        # Calculate cache key
        cache_key = self._calculate_hash(report_id, params)

        # Get report metadata to check for per-report cache TTL
        metadata = repository.get_metadata(report_id)
        cache_ttl_minutes = metadata.cache_ttl_minutes or self.cache_ttl_minutes

        async with AsyncSessionLocal() as db:
            try:
                # Check if we should skip rendering (cache hit and not force_refresh)
                if not force_refresh:
                    cutoff_time = datetime.utcnow() - timedelta(
                        minutes=cache_ttl_minutes
                    )
                    result = await db.execute(
                        select(Render).where(
                            and_(
                                Render.parameter_hash == cache_key,
                                Render.status == RenderStatus.COMPLETED.value,
                                Render.completed_at >= cutoff_time,
                            )
                        )
                    )
                    cached = result.scalar_one_or_none()
                    if cached:
                        logger.info(f"Using cached render for {cache_key[:8]} (TTL: {cache_ttl_minutes} minutes)")
                        # Return cached PDF
                        try:
                            pdf_bytes = await self.storage.retrieve(cache_key)
                            return RenderResult(
                                status=RenderStatus.COMPLETED, pdf_bytes=pdf_bytes
                            )
                        except FileNotFoundError:
                            logger.warning(
                                f"Cached PDF not found for {cache_key[:8]}, re-rendering"
                            )
                            # Continue to re-render

                logger.info(f"Starting render execution for {cache_key[:8]}")

                # Create or update render record
                result = await db.execute(
                    select(Render).where(Render.parameter_hash == cache_key)
                )
                render = result.scalar_one_or_none()

                if render:
                    # Update existing record
                    render.status = RenderStatus.RUNNING.value
                    render.started_at = datetime.utcnow()
                    render.error_message = None
                else:
                    # Create new record
                    render = Render(
                        parameter_hash=cache_key,
                        report_id=report_id,
                        parameters_json=json.dumps(params, default=str),
                        status=RenderStatus.RUNNING.value,
                        started_at=datetime.utcnow(),
                    )
                    db.add(render)

                await db.commit()

                # Get report
                report = repository.get_report(report_id)
                logger.info(f"Loaded report: {report_id}")

                # Execute queries
                query_results = await query_executor.execute_queries(report, params)
                logger.info(f"Executed {len(query_results)} queries")

                # Render template
                html = template_renderer.render(report, params, query_results)
                logger.info("Template rendered successfully")

                # Generate PDF
                pdf_bytes = await pdf_generator.generate(html)
                logger.info(f"PDF generated, size: {len(pdf_bytes)} bytes")

                # Store PDF
                pdf_path = await self.storage.save(cache_key, pdf_bytes)
                logger.info(f"PDF stored at: {pdf_path}")

                # Update status to completed
                render.status = RenderStatus.COMPLETED.value
                render.completed_at = datetime.utcnow()
                render.pdf_path = pdf_path
                render.file_size_bytes = len(pdf_bytes)
                await db.commit()

                logger.info(f"Render completed successfully: {cache_key[:8]}")

                # Return successful result
                return RenderResult(status=RenderStatus.COMPLETED, pdf_bytes=pdf_bytes)

            except Exception as e:
                logger.error(f"Render failed for {cache_key[:8]}: {e}", exc_info=True)

                # Update status to failed
                try:
                    result = await db.execute(
                        select(Render).where(Render.parameter_hash == cache_key)
                    )
                    render = result.scalar_one_or_none()

                    if render:
                        render.status = RenderStatus.FAILED.value
                        render.completed_at = datetime.utcnow()
                        render.error_message = str(e)
                        await db.commit()
                except Exception as update_error:
                    logger.error(f"Failed to update error status: {update_error}")

                # Return failed result
                return RenderResult(status=RenderStatus.FAILED, error_message=str(e))


# Global render service instance
render_service = RenderServiceImpl()
