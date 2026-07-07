"""Main render service implementation."""

import asyncio
import hashlib
import json
import logging
import re
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
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
from .renderer_registry import renderer_registry
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

    def _parse_enum_query_params(self, query_file: Path) -> List[str]:
        """Extract parameter names from enum query SQL file.
        
        Args:
            query_file: Path to SQL query file
            
        Returns:
            List of unique parameter names found in the query
        """
        try:
            with open(query_file, "r", encoding="utf-8") as f:
                query = f.read()
            
            # Find all named parameters in the query (e.g., :schema_name)
            # Exclude PostgreSQL type casts (::type) by using negative lookbehind
            named_params = re.findall(r"(?<!:):(\w+)", query)
            
            # Return unique parameter names
            return list(set(named_params))
        except Exception as e:
            logger.error(f"Failed to parse enum query file {query_file}: {e}")
            return []
        
    async def get_generator(report_id: str) -> str:
        """ Get generator for specified format """
        report = repository.get_report(report_id)
        metadata = report.metadata
        output_format = metadata.format
        logger.info(f"Loaded report: {report_id}, format: {output_format}")

        # Get appropriate generator
        return renderer_registry.get_generator(output_format)

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

        # Build initial parameter values (defaults or None)
        # Convert defaults to proper types using query executor's conversion method
        initial_params = {}
        for param in metadata_copy.parameters:
            if param.default is not None:
                # Convert default value to proper type
                initial_params[param.name] = query_executor._convert_default_value(
                    param.default, param.type
                )
            else:
                initial_params[param.name] = None

        # Resolve dynamic enums and parse dependencies
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
                    # Parse parameter dependencies from the SQL file
                    param.enum_query_params = self._parse_enum_query_params(query_file)
                    logger.info(
                        f"Parameter {param.name} enum_query depends on: {param.enum_query_params}"
                    )
                    
                    # Execute the enum query with initial parameter values
                    logger.info(f"Executing enum query from {query_file}")
                    enum_values = await query_executor.execute_enum_query(
                        query_file, initial_params
                    )
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

    async def getParameterDependencies(self, report_id: str) -> Dict[str, List[str]]:
        """Get dependency graph showing which parameters affect which enum queries.
        
        Args:
            report_id: Report identifier
            
        Returns:
            Dictionary mapping parameter names to list of dependent parameter names
        """
        # Get metadata (which includes parsed enum_query_params)
        metadata = await self.getReportMetadata(report_id)
        
        # Build reverse dependency mapping
        # Key: parameter that changes
        # Value: list of parameters whose enum queries need refresh
        dependencies: Dict[str, List[str]] = {}
        
        for param in metadata.parameters:
            if param.enum_query and param.enum_query_params:
                # This parameter has an enum query that depends on other parameters
                for dependency_param in param.enum_query_params:
                    if dependency_param not in dependencies:
                        dependencies[dependency_param] = []
                    # When dependency_param changes, param's enum needs refresh
                    if param.name not in dependencies[dependency_param]:
                        dependencies[dependency_param].append(param.name)
        
        logger.info(f"Parameter dependencies for {report_id}: {dependencies}")
        return dependencies

    async def refreshEnumValues(
        self, report_id: str, param_name: str, current_params: Dict[str, Any]
    ) -> List[Any]:
        """Refresh enum values for a specific parameter based on current parameter values.
        
        Args:
            report_id: Report identifier
            param_name: Parameter whose enum values need refresh
            current_params: Current values of all parameters
            
        Returns:
            List of updated enum values
        """
        # Get report and metadata
        report = repository.get_report(report_id)
        metadata = repository.get_metadata(report_id)
        
        # Find the parameter definition
        param_def = None
        for param in metadata.parameters:
            if param.name == param_name:
                param_def = param
                break
        
        if not param_def:
            logger.warning(f"Parameter {param_name} not found in report {report_id}")
            return []
        
        if not param_def.enum_query:
            logger.warning(f"Parameter {param_name} has no enum_query")
            return []
        
        # Get query file
        query_file = report.path / param_def.enum_query
        
        if not query_file.exists():
            logger.warning(f"Enum query file not found: {query_file}")
            return []
        
        try:
            # Execute enum query with current parameters
            logger.info(
                f"Refreshing enum values for {param_name} with params: {current_params}"
            )
            enum_values = await query_executor.execute_enum_query(
                query_file, current_params
            )
            logger.info(
                f"Refreshed {len(enum_values)} enum values for {param_name}: {enum_values[:5]}"
            )
            return enum_values
        except Exception as e:
            logger.error(
                f"Failed to refresh enum values for {param_name}: {e}",
                exc_info=True,
            )
            return []

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
                    # Valid cached result - return file path
                    if render.output_path:
                        # Use file extension from database
                        file_ext = render.file_extension
                        
                        filename = f"{cache_key}.{file_ext}"
                        return RenderResult(
                            status=RenderStatus.COMPLETED,
                            file_path=filename,
                            filename=f"{report_id}.{file_ext}"
                        )
                    else:
                        logger.warning(
                            f"Output path not found for cache key {cache_key[:8]}"
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
                        # Return cached output path
                        if cached.output_path:
                            # Use file extension from database
                            file_ext = cached.file_extension
                            
                            filename = f"{cache_key}.{file_ext}"
                            return RenderResult(
                                status=RenderStatus.COMPLETED,
                                file_path=filename,
                                filename=f"{report_id}.{file_ext}"
                            )
                        else:
                            logger.warning(
                                f"Cached output path not found for {cache_key[:8]}, re-rendering"
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
                    pass
                    '''
                    render = Render(
                        parameter_hash=cache_key,
                        report_id=report_id,
                        parameters_json=json.dumps(params, default=str),
                        status=RenderStatus.RUNNING.value,
                        started_at=datetime.utcnow(),
                        output_format=metadata.format,
                        file_extension="pdf",  # Will be updated after generation
                    )
                    db.add(render)
                    '''
                await db.commit()

                # Get report
                report = repository.get_report(report_id)
                metadata = report.metadata
                output_format = metadata.format
                
                logger.info(f"Loaded report: {report_id}, format: {output_format}")

                # Get appropriate generator
                generator = renderer_registry.get_generator(output_format)

                # Execute queries
                query_results = await query_executor.execute_queries(report, params)
                logger.info(f"Executed {len(query_results)} queries")

                # Render template
                output_bytes = await generator.render(report, params, query_results)
                logger.info("Template rendered successfully")

                file_extension = generator.file_extension
                
                logger.info(
                    f"Output generated, format: {output_format}, "
                    f"size: {len(output_bytes)} bytes, extension: {file_extension}"
                )

                # Store output
                output_path = await self.storage.save(cache_key, output_bytes, file_extension)
                logger.info(f"Output stored at: {output_path}")

                # Update status to completed
                '''
                render.status = RenderStatus.COMPLETED.value
                render.completed_at = datetime.utcnow()
                render.output_path = output_path
                render.output_format = output_format
                render.file_extension = file_extension
                render.file_size_bytes = len(output_bytes)
                await db.commit()
                '''

                logger.info(f"Render completed successfully: {cache_key[:8]}")

                # Return successful result with file path
                filename = f"{cache_key}.{file_extension}"
                return RenderResult(
                    status=RenderStatus.COMPLETED,
                    file_path=filename,
                    filename=f"{report_id}.{file_extension}"
                )

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

    async def generatePreview(
        self, report_id: str, params: Dict[str, Any]
    ) -> str:
        """
        Generate HTML preview without converting to final format.

        This method executes queries and renders the Jinja2 template to HTML,
        but skips the final format conversion (PDF/DOCX). Useful for quick
        preview during development or debugging. No caching is performed.

        Args:
            report_id: Report identifier
            params: User-provided parameters

        Returns:
            Rendered HTML content as string

        Raises:
            ValueError: If report_id does not exist
            RuntimeError: If query execution or template rendering fails
        """
        try:
            logger.info(f"Generating HTML preview for report: {report_id}")

            # Get report
            report = repository.get_report(report_id)
            logger.info(f"Loaded report: {report_id}")

            metadata = report.metadata
            output_format = metadata.format
                
            # Get appropriate generator
            generator = renderer_registry.get_generator(output_format)

            # Execute queries
            query_results = await query_executor.execute_queries(report, params)
            logger.info(f"Executed {len(query_results)} queries")

            # Render template to HTML
            html_content = await generator.render_preview(report, params, query_results)
            logger.info(f"Template rendered successfully, HTML length: {len(html_content)} chars")

            return html_content

        except Exception as e:
            logger.error(f"Preview generation failed for {report_id}: {e}", exc_info=True)
            raise RuntimeError(f"Preview generation failed: {e}")


# Global render service instance
render_service = RenderServiceImpl()
