import base64
import json
from datetime import datetime
from typing import List, Dict, Any

import reflex as rx

from render import render_service
from render.models import RenderStatus, ParameterType
from report2.models import ParamInfo
from report2.services import ensure_services_initialized, logger
from report2.auth.auth_state import AuthState


class State(AuthState):
    """Application state for PDF report generator."""

    # Report list
    reports: List[Dict[str, str]] = []

    # Selected report
    selected_report_id: str = ""
    selected_report_name: str = ""
    selected_report_description: str = ""
    report_parameters: List[ParamInfo] = []

    # Render status
    render_status: str = ""
    render_error: str = ""
    is_rendering: bool = False
    pdf_ready: bool = False

    # Current render params (for background task)
    _current_render_params: Dict[str, Any] = {}

    # Parameter dependency tracking
    # current_param_values: Dict[str, Any] = {}
    param_dependencies: Dict[str, List[str]] = {}

    # Preview navigation state
    _preview_mode: bool = False

    @rx.var
    def current_param_values(self) -> Dict[str, Any]:
        return {i.name: i.value for i in self.report_parameters}

    @rx.event
    async def load_reports(self):
        """Load all available reports on mount."""
        try:
            # Ensure services are initialized before loading reports
            await ensure_services_initialized()

            report_list = render_service.listReports()
            self.reports = [{"id": r.id, "name": r.name} for r in report_list]
        except Exception as e:
            self.render_error = f"Failed to load reports: {str(e)}"
            logger.error(f"Error loading reports: {e}", exc_info=True)

    @rx.event
    async def select_report(self, report_id: str):
        """Select a report and load its metadata."""
        try:
            # Ensure services are initialized
            await ensure_services_initialized()

            self.selected_report_id = report_id
            metadata = await render_service.getReportMetadata(report_id)

            # Store metadata in separate fields
            self.selected_report_name = metadata.name
            self.selected_report_description = metadata.description or ""

            # Convert parameters to ParamInfo objects
            self.report_parameters = [
                ParamInfo(
                    name=p.name,
                    type=p.type.value,
                    required=p.required,
                    description=p.description or p.name,
                    placeholder=p.placeholder or "",
                    enum_values=p.enum or [],
                    value=str(p.default) if p.default is not None else "",  # Initialize value with default
                )
                for p in metadata.parameters
            ]

            # Initialize current parameter values with defaults
            # self.current_param_values = {
            #     p.name: p.default for p in metadata.parameters
            # }

            # Load parameter dependency graph from service
            self.param_dependencies = await render_service.getParameterDependencies(report_id)
            logger.info(f"Loaded parameter dependencies: {self.param_dependencies}")

            # Reset render state
            self.render_status = ""
            self.render_error = ""
            self.is_rendering = False
            self.pdf_ready = False

        except Exception as e:
            self.render_error = f"Failed to load report metadata: {str(e)}"
            logger.error(f"Error in select_report: {e}", exc_info=True)

    @rx.event
    async def handle_input_changed(self, parameter_name: str, value: Any):
        """Handle parameter value changes and refresh dependent enum queries."""
        logger.info(f"Input {parameter_name} value changed to {value}")

        try:
            # Ensure services are initialized
            await ensure_services_initialized()

            # Update the value in ParamInfo
            for param_info in self.report_parameters:
                if param_info.name == parameter_name:
                    param_info.value = str(value)
                    break

            # Update current parameter values (still needed for enum queries)
            # self.current_param_values[parameter_name] = value

            # Check if any parameters depend on this one
            dependent_params = self.param_dependencies.get(parameter_name, [])

            if not dependent_params:
                logger.info(f"No dependent parameters for {parameter_name}")
                return

            logger.info(f"Refreshing enum values for dependent parameters: {dependent_params}")

            # Refresh enum values for each dependent parameter
            for param_name in dependent_params:
                try:
                    new_enum_values = await render_service.refreshEnumValues(
                        self.selected_report_id,
                        param_name,
                        self.current_param_values
                    )

                    # Update the parameter's enum values in state
                    for param_info in self.report_parameters:
                        if param_info.name == param_name:
                            param_info.enum_values = new_enum_values
                            logger.info(
                                f"Updated enum values for {param_name}: {len(new_enum_values)} values"
                            )
                            break

                except Exception as e:
                    logger.error(
                        f"Failed to refresh enum values for {param_name}: {e}",
                        exc_info=True
                    )
                    # Continue with other dependent parameters

        except Exception as e:
            logger.error(f"Error in handle_input_changed: {e}", exc_info=True)

    @rx.event
    async def handle_submit(self, form_data: dict):
        """Handle form submission - either preview or generate based on _preview_mode."""
        if not self.selected_report_id:
            self.render_error = "No report selected"
            return

        try:
            # Ensure services are initialized
            await ensure_services_initialized()

            # Convert form params to appropriate types
            typed_params = self._convert_params(form_data)

            # Check if this is preview mode
            if self._preview_mode:
                # Reset preview mode flag
                self._preview_mode = False
                # Navigate to preview page with parameters
                # Use default=str to handle date/datetime objects
                params_json = json.dumps(typed_params, default=str)
                params_encoded = base64.urlsafe_b64encode(params_json.encode()).decode()
                return rx.redirect(
                    f"/preview?report_id={self.selected_report_id}&params={params_encoded}"
                )
            else:
                # Handle generate
                # Store params in state for background task
                self._current_render_params = typed_params

                # Reset state
                self.render_status = "Starting render..."
                self.render_error = ""
                self.is_rendering = True
                self.pdf_ready = False

                # Start background render task
                return State.render_report

        except Exception as e:
            self.render_error = f"Failed to start: {str(e)}"
            self.is_rendering = False
            self._preview_mode = False
            logger.error(f"Error in handle_submit: {e}", exc_info=True)

    @rx.event
    def set_preview_mode(self):
        """Set flag to indicate preview button was clicked."""
        self._preview_mode = True

    @rx.event(background=True)
    async def render_report(self):
        """Execute report rendering in background."""
        async with self:
            if not self.selected_report_id:
                return
            report_id = self.selected_report_id
            typed_params = self._current_render_params

        try:
            # Update status
            async with self:
                self.render_status = "Rendering..."

            # Execute render directly - no polling needed
            result = await render_service.executeRender(
                report_id, typed_params, force_refresh=False
            )

            # Update state with result
            async with self:
                if result.status == RenderStatus.COMPLETED:
                    self.render_status = "Completed!"
                    self.is_rendering = False
                    self.pdf_ready = True
                    # Initiate file download using Reflex's upload URL mechanism
                    if result.file_path:
                        download_url = rx.get_upload_url(result.file_path)
                        return rx.download(url=download_url, filename=result.filename)
                elif result.status == RenderStatus.FAILED:
                    self.render_status = "Failed"
                    self.render_error = result.error_message or "Unknown error"
                    self.is_rendering = False

        except Exception as e:
            async with self:
                self.render_error = f"Render error: {str(e)}"
                self.is_rendering = False
                logger.error(f"Error in render_report: {e}", exc_info=True)

    @rx.event
    def close_preview(self):
        """Close the preview dialog."""
        self.show_preview_dialog = False
        self.preview_html = ""

    def _convert_params(self, form_data: dict) -> Dict[str, Any]:
        """Convert form string params to typed values."""
        if not self.report_parameters:
            return {}

        typed_params = {}
        for param_def in self.report_parameters:
            param_name = param_def.name
            param_type = param_def.type
            value_str = form_data.get(param_name, "")

            # Special handling for boolean - always include it (switch can be on/off)
            if param_type == ParameterType.BOOLEAN.value:
                # If value_str is truthy (switch is on), it will be "on" or "true"
                # If switch is off, value_str will be empty string
                typed_params[param_name] = (
                    value_str.lower() in ("true", "1", "yes", "on")
                    if value_str
                    else False
                )
                continue

            # Skip empty non-required params (except boolean which is handled above)
            if not value_str and not param_def.required:
                continue

            # Convert based on type
            try:
                if param_type == ParameterType.STRING.value:
                    typed_params[param_name] = value_str
                elif param_type == ParameterType.INTEGER.value:
                    if value_str:
                        # Convert to float first, then to int to handle decimal inputs
                        typed_params[param_name] = int(float(value_str))
                    else:
                        typed_params[param_name] = 0
                elif param_type == ParameterType.FLOAT.value:
                    typed_params[param_name] = float(value_str) if value_str else 0.0
                elif param_type == ParameterType.DATE.value:
                    # Convert date string (YYYY-MM-DD) to date object
                    if value_str:
                        typed_params[param_name] = datetime.strptime(
                            value_str, "%Y-%m-%d"
                        ).date()
                elif param_type == ParameterType.DATETIME.value:
                    # Convert datetime string (YYYY-MM-DDTHH:MM) to datetime object
                    if value_str:
                        typed_params[param_name] = datetime.strptime(
                            value_str, "%Y-%m-%dT%H:%M"
                        )
            except ValueError as e:
                raise ValueError(f"Invalid value for {param_name}: {e}")

        return typed_params
