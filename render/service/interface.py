from typing import List, Dict, Any
from ..models import ReportListItem, ReportMetadata, RenderResult
from abc import ABC, abstractmethod


class RenderService(ABC):
    """Abstract interface for PDF report rendering service.
    
    This service provides methods to discover available reports, retrieve their
    metadata and parameters, and render them as PDF files. Rendering is performed
    asynchronously in the background with intelligent caching to handle long-running
    operations efficiently.
    
    Caching Strategy:
        Reports are cached based on report_id and parameters. The cache has an
        expiration time, after which reports are automatically re-rendered.
        Use force_refresh=True to bypass cache and trigger immediate re-rendering.
    
    Typical usage flow:
        1. Call listReports() to get available reports
        2. Call getReportMetadata(report_id) to get parameter definitions
        3. Call startRender(report_id, params) to begin rendering in background
        4. Poll getRenderStatus(report_id, params) until status is COMPLETED or FAILED
        5. Extract PDF bytes from result or display error message
    """

    @abstractmethod
    def listReports(self) -> List[ReportListItem]:
        """Get list of all available reports.
        
        Returns:
            List of ReportListItem objects containing basic report information
            (id and name) for all reports available in the system.
            
        Example:
            >>> reports = service.listReports()
            >>> for report in reports:
            ...     print(f"{report.id}: {report.name}")
        """
        pass

    @abstractmethod
    def getReportMetadata(self, report_id: str) -> ReportMetadata:
        """Get detailed metadata for a specific report.
        
        Provides comprehensive information about a report including its parameters,
        description, version, and timeout settings. Use this to build dynamic forms
        for parameter input.
        
        Args:
            report_id: Unique identifier of the report
            
        Returns:
            ReportMetadata object containing full report details including
            parameter definitions with types, validation rules, and defaults.
            
        Raises:
            ValueError: If report_id does not exist
            
        Example:
            >>> metadata = service.getReportMetadata("sales-report")
            >>> for param in metadata.parameters:
            ...     print(f"{param.name}: {param.type} (required={param.required})")
        """
        pass

    @abstractmethod
    def startRender(self, report_id: str, params: Dict[str, Any], force_refresh: bool = False) -> None:
        """Start rendering a report in the background.
        
        Initiates asynchronous PDF generation with the provided parameters.
        This method returns immediately. Use getRenderStatus() with the same
        report_id and params to check progress and retrieve results.
        
        The service uses intelligent caching: if a non-expired cached version
        exists for the given report_id and params, it will be reused unless
        force_refresh is True.
        
        Args:
            report_id: Unique identifier of the report to render
            params: Dictionary of parameter values matching the report's
                   parameter definitions. Keys should match parameter names,
                   values should match parameter types.
            force_refresh: If True, bypasses cache and forces fresh re-rendering
                          even if a valid cached version exists. Default is False.
                   
        Raises:
            ValueError: If report_id does not exist or parameters are invalid
            
        Example:
            >>> service.startRender(
            ...     "sales-report",
            ...     {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            ...     force_refresh=True
            ... )
            >>> # Now poll getRenderStatus() with same report_id and params
        """
        pass

    @abstractmethod
    def getRenderStatus(self, report_id: str, params: Dict[str, Any]) -> RenderResult:
        """Get the current status and result of a report rendering.
        
        This method checks for cached results first. If a non-expired cached
        version exists for the given report_id and params, it returns immediately
        with COMPLETED status. Otherwise, it checks the status of any ongoing
        rendering job or returns PENDING if no job has been started yet.
        
        Poll this method repeatedly to check if rendering is complete. When status
        is COMPLETED, the result will contain PDF bytes. When status is FAILED,
        the result will contain an error message.
        
        Args:
            report_id: Unique identifier of the report
            params: Dictionary of parameter values used for rendering.
                   Must match the params passed to startRender().
            
        Returns:
            RenderResult object containing:
            - status: PENDING (not started), RUNNING (in progress),
                     COMPLETED (finished successfully), or FAILED (error occurred)
            - pdf_bytes: PDF content (only when status is COMPLETED)
            - error_message: Error description (only when status is FAILED)
            
        Raises:
            ValueError: If report_id does not exist
            
        Example:
            >>> # After calling startRender()
            >>> result = service.getRenderStatus(
            ...     "sales-report",
            ...     {"start_date": "2024-01-01", "end_date": "2024-12-31"}
            ... )
            >>> if result.status == RenderStatus.COMPLETED:
            ...     with open("report.pdf", "wb") as f:
            ...         f.write(result.pdf_bytes)
            >>> elif result.status == RenderStatus.FAILED:
            ...     print(f"Error: {result.error_message}")
            >>> elif result.status == RenderStatus.RUNNING:
            ...     print("Still rendering, please wait...")
            >>> else:  # PENDING
            ...     print("Not started yet, call startRender() first")
        """
        pass

