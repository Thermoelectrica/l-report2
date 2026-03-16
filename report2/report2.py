"""PDF Report Generator - Reflex Web Application."""

import reflex as rx
from typing import Dict, Any, List
import asyncio
import base64
import logging

from rxconfig import config
from render.services.render_service import render_service
from render.services.query_executor import query_executor
from render.database import init_db, close_db
from render.models import (
    ReportListItem,
    ReportMetadata,
    ReportParameter,
    ParameterType,
    RenderStatus,
    RenderResult,
)

logger = logging.getLogger(__name__)

# Flag to track if services are initialized
_services_initialized = False
_initialization_lock = asyncio.Lock()


async def ensure_services_initialized():
    """Ensure all services are initialized (idempotent)."""
    global _services_initialized
    
    async with _initialization_lock:
        if not _services_initialized:
            logger.info("Initializing services...")
            try:
                # Initialize database
                await init_db()
                logger.info("Database initialized")
                
                # Initialize query executor
                await query_executor.initialize()
                logger.info("Query executor initialized")
                
                _services_initialized = True
                logger.info("All services initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize services: {e}", exc_info=True)
                raise


class ParamInfo(rx.Base):
    """Parameter information for UI rendering."""
    name: str
    type: str
    required: bool
    description: str
    enum_values: List[str] = []
    default_value: str = ""


class State(rx.State):
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
    def select_report(self, report_id: str):
        """Select a report and load its metadata."""
        try:
            self.selected_report_id = report_id
            metadata = render_service.getReportMetadata(report_id)
            
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
                    enum_values=p.enum or [],
                    default_value=str(p.default) if p.default is not None else "",
                )
                for p in metadata.parameters
            ]
            
            # Reset render state
            self.render_status = ""
            self.render_error = ""
            self.is_rendering = False
            self.pdf_ready = False
            
        except Exception as e:
            self.render_error = f"Failed to load report metadata: {str(e)}"

    @rx.event
    async def handle_submit(self, form_data: dict):
        """Handle form submission and start PDF rendering."""
        if not self.selected_report_id:
            self.render_error = "No report selected"
            return
        
        try:
            # Ensure services are initialized
            await ensure_services_initialized()
            
            # Convert form params to appropriate types
            typed_params = self._convert_params(form_data)
            
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
            self.render_error = f"Failed to start render: {str(e)}"
            self.is_rendering = False
            logger.error(f"Error in handle_submit: {e}", exc_info=True)


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
                self.render_status = "Rendering PDF..."
            
            # Execute render directly - no polling needed
            result = await render_service.executeRender(
                report_id,
                typed_params,
                force_refresh=False
            )
            
            # Update state with result
            async with self:
                if result.status == RenderStatus.COMPLETED:
                    self.render_status = "Completed!"
                    self.is_rendering = False
                    self.pdf_ready = True
                    # Initiate file download
                    return rx.download(data=result.pdf_bytes, filename=f"{report_id}.pdf")
                elif result.status == RenderStatus.FAILED:
                    self.render_status = "Failed"
                    self.render_error = result.error_message or "Unknown error"
                    self.is_rendering = False
                
        except Exception as e:
            async with self:
                self.render_error = f"Render error: {str(e)}"
                self.is_rendering = False
                logger.error(f"Error in render_report: {e}", exc_info=True)

    def _convert_params(self, form_data: dict) -> Dict[str, Any]:
        """Convert form string params to typed values."""
        if not self.report_parameters:
            return {}
        
        typed_params = {}
        for param_def in self.report_parameters:
            param_name = param_def.name
            param_type = param_def.type
            value_str = form_data.get(param_name, "")
            
            # Skip empty non-required params
            if not value_str and not param_def.required:
                continue
            
            # Convert based on type
            try:
                if param_type == ParameterType.STRING.value:
                    typed_params[param_name] = value_str
                elif param_type == ParameterType.INTEGER.value:
                    typed_params[param_name] = int(value_str) if value_str else 0
                elif param_type == ParameterType.FLOAT.value:
                    typed_params[param_name] = float(value_str) if value_str else 0.0
                elif param_type == ParameterType.BOOLEAN.value:
                    typed_params[param_name] = value_str.lower() in ("true", "1", "yes", "on")
                elif param_type in (ParameterType.DATE.value, ParameterType.DATETIME.value):
                    typed_params[param_name] = value_str
            except ValueError as e:
                raise ValueError(f"Invalid value for {param_name}: {e}")
        
        return typed_params


def report_list_item(report: Dict[str, str]) -> rx.Component:
    """Render a single report list item."""
    return rx.box(
        rx.text(
            report["name"],
            size="3",
            weight="medium",
        ),
        padding="12px",
        border_radius="8px",
        background=rx.cond(
            State.selected_report_id == report["id"],
            "var(--accent-3)",
            "var(--gray-2)",
        ),
        cursor="pointer",
        _hover={"background": "var(--accent-2)"},
        on_click=State.select_report(report["id"]),
    )


def parameter_input(param: ParamInfo) -> rx.Component:
    """Render input field for a parameter based on its type."""
    # Label with required indicator and type hint
    label = rx.hstack(
        rx.text(
            param.description,
            size="2",
            weight="medium",
        ),
        rx.cond(
            param.required,
            rx.badge("Required", color_scheme="red", size="1"),
            rx.fragment(),
        ),
        rx.badge(param.type, size="1", variant="soft"),
        spacing="2",
    )
    
    # Build input field based on type
    input_field = rx.cond(
        param.enum_values,
        # Dropdown for enum values
        rx.select(
            param.enum_values,
            name=param.name,
            default_value=param.default_value,
            placeholder=f"Select {param.name}",
        ),
        # Input field based on type
        rx.input(
            name=param.name,
            default_value=param.default_value,
            placeholder=f"Enter {param.name}",
            type=rx.cond(
                param.type == ParameterType.DATE.value,
                "date",
                rx.cond(
                    param.type == ParameterType.DATETIME.value,
                    "datetime-local",
                    rx.cond(
                        (param.type == ParameterType.INTEGER.value) | (param.type == ParameterType.FLOAT.value),
                        "number",
                        "text",
                    ),
                ),
            ),
            required=param.required,
        ),
    )
    
    return rx.vstack(
        label,
        input_field,
        spacing="2",
        align_items="start",
        width="100%",
    )


def report_details_panel() -> rx.Component:
    """Render the right panel with report details and form."""
    return rx.cond(
        State.selected_report_id != "",
        rx.vstack(
            # Report header
            rx.heading(
                State.selected_report_name,
                size="6",
            ),
            rx.cond(
                State.selected_report_description != "",
                rx.text(
                    State.selected_report_description,
                    size="2",
                    color="gray",
                ),
                rx.fragment(),
            ),
            rx.divider(),
            
            # Parameters form
            rx.form(
                rx.vstack(
                    rx.heading("Parameters", size="4"),
                    rx.cond(
                        State.report_parameters,
                        rx.vstack(
                            rx.foreach(
                                State.report_parameters,
                                parameter_input,
                            ),
                            spacing="4",
                            width="100%",
                        ),
                        rx.text("No parameters required", size="2", color="gray"),
                    ),
                    
                    # Submit button
                    rx.button(
                        "Generate PDF",
                        type="submit",
                        disabled=State.is_rendering,
                        size="3",
                        width="100%",
                    ),
                    
                    spacing="4",
                    width="100%",
                ),
                on_submit=State.handle_submit,
                width="100%",
            ),
            
            # Status display
            rx.cond(
                State.render_status != "",
                rx.callout(
                    State.render_status,
                    icon="info",
                    color_scheme="blue",
                ),
                rx.fragment(),
            ),
            
            # Error display
            rx.cond(
                State.render_error != "",
                rx.callout(
                    State.render_error,
                    icon="alert-triangle",
                    color_scheme="red",
                ),
                rx.fragment(),
            ),
            
            spacing="4",
            align_items="start",
            width="100%",
        ),
        # No report selected
        rx.vstack(
            rx.icon("file-text", size=48, color="gray"),
            rx.text(
                "Select a report from the list",
                size="4",
                color="gray",
            ),
            spacing="4",
            align_items="center",
            justify="center",
            height="100%",
        ),
    )


def index() -> rx.Component:
    """Main page with two-column layout."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            # Header
            rx.heading("PDF Report Generator", size="8"),
            rx.text(
                "Select a report and configure parameters to generate PDF",
                size="3",
                color="gray",
            ),
            
            # Two-column layout
            rx.grid(
                # Left column - Report list
                rx.box(
                    rx.vstack(
                        rx.heading("Available Reports", size="5"),
                        rx.divider(),
                        rx.cond(
                            State.reports,
                            rx.vstack(
                                rx.foreach(State.reports, report_list_item),
                                spacing="2",
                                width="100%",
                            ),
                            rx.text("Loading reports...", size="2", color="gray"),
                        ),
                        spacing="3",
                        align_items="start",
                        width="100%",
                    ),
                    padding="20px",
                    border_radius="12px",
                    border="1px solid var(--gray-5)",
                    background="var(--gray-1)",
                    height="600px",
                    overflow_y="auto",
                ),
                
                # Right column - Report details and form
                rx.box(
                    report_details_panel(),
                    padding="20px",
                    border_radius="12px",
                    border="1px solid var(--gray-5)",
                    background="var(--gray-1)",
                    height="600px",
                    overflow_y="auto",
                ),
                
                columns="2",
                spacing="4",
                width="100%",
            ),
            
            spacing="5",
            width="100%",
            max_width="1400px",
            padding="20px",
        ),
        on_mount=State.load_reports,
    )


app = rx.App()
app.add_page(index)
