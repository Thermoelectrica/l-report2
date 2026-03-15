"""Render orchestration service."""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models.database import Render
from models.schemas import RenderStatus
from .pdf_generator import pdf_generator
from .query_executor import query_executor
from .repository import repository
from .template_renderer import template_renderer

logger = logging.getLogger(__name__)


class RenderService:
    """Orchestrate the complete render workflow."""

    # Cache TTL in hours - renders older than this won't be reused
    CACHE_TTL_HOURS = 24

    def calculate_parameter_hash(
        self, report_id: str, parameters: Dict[str, Any]
    ) -> str:
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
        # Sort keys to ensure consistent hash, use default handler for non-serializable types
        json_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(json_str.encode()).hexdigest()

    async def find_cached_render(
        self, db: AsyncSession, report_id: str, parameter_hash: str
    ) -> Optional[Render]:
        """
        Find a recent completed render with the same parameters.

        Args:
            db: Database session
            report_id: Report template ID
            parameter_hash: Hash of parameters

        Returns:
            Cached render if found, None otherwise
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=self.CACHE_TTL_HOURS)

        result = await db.execute(
            select(Render)
            .where(
                and_(
                    Render.report_id == report_id,
                    Render.parameter_hash == parameter_hash,
                    Render.status == RenderStatus.COMPLETED.value,
                    Render.completed_at >= cutoff_time,
                )
            )
            .order_by(Render.completed_at.desc())
            .limit(1)
        )

        cached_render = result.scalar_one_or_none()

        if cached_render:
            logger.info(
                f"Found cached render {cached_render.id} for report {report_id} "
                f"with hash {parameter_hash}"
            )

        return cached_render

    async def execute_render(
        self, render_id: UUID, report_id: str, parameters: Dict[str, Any]
    ):
        """
        Execute complete render workflow.

        This is the main background task that:
        1. Updates status to processing
        2. Executes SQL queries
        3. Renders Jinja2 template
        4. Generates PDF
        5. Stores PDF
        6. Updates status to completed/failed

        Args:
            render_id: Unique render identifier
            report_id: Report template ID
            parameters: User-provided parameters
        """
        async with AsyncSessionLocal() as db:
            try:
                logger.info(f"Starting render execution: {render_id}")

                # Update status to processing
                await self._update_status(
                    db, render_id, RenderStatus.PROCESSING, started_at=datetime.utcnow()
                )

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
                pdf_path = await storage.save(render_id, pdf_bytes)
                logger.info(f"PDF stored at: {pdf_path}")

                # Update status to completed
                await self._update_status(
                    db,
                    render_id,
                    RenderStatus.COMPLETED,
                    completed_at=datetime.utcnow(),
                    pdf_path=pdf_path,
                    file_size_bytes=len(pdf_bytes),
                )

                logger.info(f"Render completed successfully: {render_id}")

            except Exception as e:
                logger.error(f"Render failed: {render_id}, error: {e}", exc_info=True)

                # Update status to failed
                await self._update_status(
                    db,
                    render_id,
                    RenderStatus.FAILED,
                    completed_at=datetime.utcnow(),
                    error_message=str(e),
                )

    async def _update_status(
        self, db: AsyncSession, render_id: UUID, status: RenderStatus, **kwargs
    ):
        """Update render status in database."""
        try:
            result = await db.execute(select(Render).where(Render.id == render_id))
            render = result.scalar_one_or_none()

            if render:
                render.status = status.value
                for key, value in kwargs.items():
                    setattr(render, key, value)
                await db.commit()
                logger.debug(f"Updated render {render_id} status to {status.value}")
            else:
                logger.error(f"Render not found: {render_id}")

        except Exception as e:
            logger.error(f"Failed to update render status: {e}")
            await db.rollback()
            raise


# Global render service instance
render_service = RenderService()
