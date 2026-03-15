"""Main render service implementation."""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import select, and_

from ..database import AsyncSessionLocal
from ..database.models import Render
from ..models import RenderStatus, RenderResult, ReportListItem, ReportMetadata
from ..service.interface import RenderService as RenderServiceInterface
from ..storage import get_storage
from .repository import repository
from .query_executor import query_executor
from .template_renderer import template_renderer
from .pdf_generator import pdf_generator

logger = logging.getLogger(__name__)


class RenderServiceImpl(RenderServiceInterface):
    """Implementation of RenderService interface."""

    def __init__(self, cache_ttl_hours: int = 24):
        """
        Initialize render service.
        
        Args:
            cache_ttl_hours: Cache time-to-live in hours
        """
        self.cache_ttl_hours = cache_ttl_hours
        self.storage = get_storage()
        self._background_tasks = set()

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

    def getReportMetadata(self, report_id: str) -> ReportMetadata:
        """Get detailed metadata for a specific report."""
        return repository.get_metadata(report_id)

    def startRender(
        self, report_id: str, params: Dict[str, Any], force_refresh: bool = False
    ) -> None:
        """Start rendering a report in the background."""
        # Calculate cache key
        cache_key = self._calculate_hash(report_id, params)
        
        # Create background task
        task = asyncio.create_task(
            self._execute_render(report_id, params, cache_key, force_refresh)
        )
        
        # Keep reference to prevent garbage collection
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        
        logger.info(f"Started render for report {report_id} with hash {cache_key[:8]}")

    def getRenderStatus(self, report_id: str, params: Dict[str, Any]) -> RenderResult:
        """Get the current status and result of a report rendering."""
        # Calculate cache key
        cache_key = self._calculate_hash(report_id, params)
        
        # Run async operation in sync context
        return asyncio.run(self._get_render_status_async(cache_key))

    async def _get_render_status_async(self, cache_key: str) -> RenderResult:
        """Async implementation of getRenderStatus."""
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
                cutoff_time = datetime.utcnow() - timedelta(hours=self.cache_ttl_hours)
                
                if render.completed_at and render.completed_at >= cutoff_time:
                    # Valid cached result - retrieve PDF
                    try:
                        pdf_bytes = await self.storage.retrieve(cache_key)
                        return RenderResult(
                            status=RenderStatus.COMPLETED,
                            pdf_bytes=pdf_bytes
                        )
                    except FileNotFoundError:
                        logger.warning(f"PDF file not found for cache key {cache_key[:8]}")
                        # Mark as pending to trigger re-render
                        return RenderResult(status=RenderStatus.PENDING)
                else:
                    # Expired cache
                    logger.info(f"Cache expired for {cache_key[:8]}")
                    return RenderResult(status=RenderStatus.PENDING)

            elif render.status == RenderStatus.FAILED.value:
                return RenderResult(
                    status=RenderStatus.FAILED,
                    error_message=render.error_message
                )

            elif render.status == RenderStatus.RUNNING.value:
                return RenderResult(status=RenderStatus.RUNNING)

            else:  # PENDING
                return RenderResult(status=RenderStatus.PENDING)

    async def _execute_render(
        self,
        report_id: str,
        parameters: Dict[str, Any],
        cache_key: str,
        force_refresh: bool
    ):
        """
        Execute complete render workflow in background.

        Args:
            report_id: Report template ID
            parameters: User-provided parameters
            cache_key: SHA256 hash for caching
            force_refresh: Whether to bypass cache
        """
        async with AsyncSessionLocal() as db:
            try:
                # Check if we should skip rendering (cache hit and not force_refresh)
                if not force_refresh:
                    cutoff_time = datetime.utcnow() - timedelta(hours=self.cache_ttl_hours)
                    result = await db.execute(
                        select(Render).where(
                            and_(
                                Render.parameter_hash == cache_key,
                                Render.status == RenderStatus.COMPLETED.value,
                                Render.completed_at >= cutoff_time
                            )
                        )
                    )
                    cached = result.scalar_one_or_none()
                    if cached:
                        logger.info(f"Using cached render for {cache_key[:8]}")
                        return

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
                        parameters_json=json.dumps(parameters, default=str),
                        status=RenderStatus.RUNNING.value,
                        started_at=datetime.utcnow(),
                    )
                    db.add(render)

                await db.commit()

                # Get report
                report = repository.get_report(report_id)
                logger.info(f"Loaded report: {report_id}")

                # Execute queries
                query_results = await query_executor.execute_queries(report, parameters)
                logger.info(f"Executed {len(query_results)} queries")

                # Render template
                html = template_renderer.render(report, parameters, query_results)
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


# Global render service instance
render_service = RenderServiceImpl()
