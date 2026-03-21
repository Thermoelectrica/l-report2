import base64
import json
from datetime import datetime
from typing import Dict, Any, List

import reflex as rx

from render import render_service
from render.models import ReportParameter, ParameterType
from report2.services import ensure_services_initialized, logger


class PreviewState(rx.State):
    """State for the preview page."""

    # Preview data
    preview_html: str = ""
    is_loading: bool = False
    error_message: str = ""

    # Decoded parameters for display
    parameters_dict: Dict[str, Any] = {}
    report_name: str = ""
    report_id: str = ""

    @rx.event
    async def load_preview(self):
        """Load and generate preview from URL parameters."""
        try:
            # Ensure services are initialized
            await ensure_services_initialized()

            self.is_loading = True
            self.error_message = ""

            # Get URL parameters from router
            report_id = self.router.page.params.get("report_id", "")
            params_encoded = self.router.page.params.get("params", "")

            # Check if params is empty
            if not params_encoded or not report_id:
                self.error_message = "Missing report_id or params in URL"
                self.is_loading = False
                return

            self.report_id = report_id

            # Decode parameters (these are strings from JSON)
            params_json = base64.urlsafe_b64decode(params_encoded.encode()).decode()
            params_dict_str = json.loads(params_json)
            self.parameters_dict = params_dict_str

            # Get report metadata for name and parameter types
            metadata = await render_service.getReportMetadata(report_id)
            self.report_name = metadata.name

            # Convert string parameters back to proper types
            typed_params = self._convert_string_params(params_dict_str, metadata.parameters)

            # Generate preview with typed parameters
            html_content = await render_service.generatePreview(
                report_id, typed_params
            )

            self.preview_html = html_content
            self.is_loading = False

        except Exception as e:
            self.error_message = f"Failed to generate preview: {str(e)}"
            self.is_loading = False
            logger.error(f"Error in load_preview: {e}", exc_info=True)

    def _convert_string_params(self, params_dict: Dict[str, Any], param_defs: List[ReportParameter]) -> Dict[str, Any]:
        """Convert string parameters from JSON back to proper types."""
        typed_params = {}

        for param_def in param_defs:
            param_name = param_def.name
            value_str = params_dict.get(param_name)

            if value_str is None:
                continue

            # Convert based on type
            try:
                if param_def.type == ParameterType.STRING:
                    typed_params[param_name] = str(value_str)
                elif param_def.type == ParameterType.INTEGER:
                    typed_params[param_name] = int(value_str)
                elif param_def.type == ParameterType.FLOAT:
                    typed_params[param_name] = float(value_str)
                elif param_def.type == ParameterType.BOOLEAN:
                    typed_params[param_name] = bool(value_str)
                elif param_def.type == ParameterType.DATE:
                    # Convert date string (YYYY-MM-DD) to date object
                    if isinstance(value_str, str):
                        typed_params[param_name] = datetime.strptime(value_str, "%Y-%m-%d").date()
                    else:
                        typed_params[param_name] = value_str
                elif param_def.type == ParameterType.DATETIME:
                    # Convert datetime string to datetime object
                    if isinstance(value_str, str):
                        # Try different formats
                        for fmt in ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M"]:
                            try:
                                typed_params[param_name] = datetime.strptime(value_str, fmt)
                                break
                            except ValueError:
                                continue
                    else:
                        typed_params[param_name] = value_str
                else:
                    typed_params[param_name] = value_str
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert parameter {param_name}: {e}, using string value")
                typed_params[param_name] = value_str

        return typed_params
