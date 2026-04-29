from typing import Dict, Any

import reflex as rx

from render.models import ParameterType
from report2.main.main_state import State
from report2.models import ParamInfo


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
    # Label with required indicator
    label = rx.box(
        rx.hstack(
            rx.cond(
                param.required,
                rx.text(
                    "*",
                    size="2",
                    color="red",
                    weight="bold",
                ),
                rx.fragment(),
            ),
            rx.text(
                param.description,
                size="2",
                weight="medium",
                align="right",
            ),
            spacing="1",
        ),
        width="50%",
        display="flex",
        align_items="center",
        justify_content="flex-end",
        padding_right="8px",
    )

    input_field = rx.match(
        param.type,
        (
            ParameterType.DATE.value,
            rx.input(
                name=param.name,
                value=param.value,
                placeholder=f"Enter {param.name}",
                type="date",
                required=param.required,
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
        ),
        (
            ParameterType.DATETIME.value,
            rx.input(
                name=param.name,
                value=param.value,
                placeholder=f"Enter {param.name}",
                type="datetime-local",
                required=param.required,
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
        ),
        (
            ParameterType.INTEGER.value,
            rx.hstack(
                rx.input(
                    name=param.name,
                    value=param.value,
                    placeholder=f"Enter {param.name}",
                    type="number",
                    step="1",
                    required=param.required,
                    on_change=lambda v: State.handle_input_changed(param.name, v)
                ),
                rx.badge(
                    "Integer only",
                    color_scheme="blue",
                    variant="soft",
                ),
                spacing="2",
                align_items="center",
            ),
        ),
        (
            ParameterType.FLOAT.value,
            rx.input(
                name=param.name,
                value=param.value,
                placeholder=f"Enter {param.name}",
                type="number",
                step="any",
                required=param.required,
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
        ),
        (
            ParameterType.BOOLEAN.value,
            rx.switch(
                name=param.name,
                checked=rx.cond(param.value == "True", True, False),
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
        ),
        rx.cond(
            param.enum_values,
            # Dropdown for enum values
            rx.select(
                param.enum_values,
                name=param.name,
                value=param.value,
                placeholder=f"Select {param.name}",
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
            # Plain text box
            rx.input(
                name=param.name,
                value=param.value,
                placeholder=f"Enter {param.name}",
                type="text",
                width="48%",
                required=param.required,
                on_change=lambda v: State.handle_input_changed(param.name, v)
            ),
        ),
    )

    return rx.hstack(
        label,
        input_field,
        spacing="2",
        width="100%",
        align_items="center",
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
                    # Action buttons
                    rx.hstack(
                        rx.button(
                            "Preview",
                            type="submit",
                            on_click=State.set_preview_mode,
                            disabled=State.is_rendering,
                            size="3",
                            variant="soft",
                            flex="1",
                        ),
                        rx.button(
                            "Generate",
                            type="submit",
                            disabled=State.is_rendering,
                            loading=State.is_rendering,
                            size="3",
                            flex="1",
                        ),
                        spacing="3",
                        width="100%",
                    ),
                    spacing="4",
                    width="100%",
                ),
                on_submit=State.handle_submit,
                width="100%",
                key=State.selected_report_id,
                reset_on_submit=False,
            ),
            # Status display (only show if no error)
            rx.cond(
                (State.render_status != "") & (State.render_error == ""),
                rx.callout(
                    State.render_status,
                    icon=rx.cond(
                        State.render_status == "Completed!",
                        "check-circle",
                        rx.cond(State.is_rendering, "loader", "info"),
                    ),
                    color_scheme=rx.cond(
                        State.render_status == "Completed!",
                        "green",
                        rx.cond(State.render_status == "Failed", "red", "blue"),
                    ),
                    width="100%",
                ),
                rx.fragment(),
            ),
            # Error display
            rx.cond(
                State.render_error != "",
                rx.callout(
                    State.render_error,
                    icon="badge_alert",
                    color_scheme="red",
                    width="100%",
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
            # Header with user info and logout
            rx.hstack(
                rx.vstack(
                    rx.heading("PDF Report Generator", size="8"),
                    rx.text(
                        "Select a report and configure parameters to generate PDF",
                        size="3",
                        color="gray",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.link(
                        rx.icon_button(
                            rx.icon("activity"),
                            size="2",
                            variant="soft",
                            color_scheme="gray",
                        ),
                        href="/status",
                        title="Status Page",
                    ),
                    rx.cond(
                        State.username != "",
                        rx.text(
                            State.username,
                            size="2",
                            weight="medium",
                        ),
                    ),
                    rx.icon_button(
                        rx.icon("log-out"),
                        on_click=State.logout,
                        size="2",
                        variant="soft",
                        color_scheme="red",
                    ),
                    spacing="3",
                    align_items="center",
                ),
                width="100%",
                align_items="center",
            ),
            # Two-column layout
            rx.hstack(
                # Left column - Report list
                rx.box(
                    rx.vstack(
                        rx.heading("Отчеты", size="5"),
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
                    overflow_y="auto",
                    width="30%",
                ),
                # Right column - Report details and form
                rx.box(
                    report_details_panel(),
                    padding="20px",
                    border_radius="12px",
                    border="1px solid var(--gray-5)",
                    background="var(--gray-1)",
                    overflow_y="auto",
                    width="70%",
                ),
                spacing="4",
                width="100%",
            ),
            spacing="5",
            width="100%",
            padding="20px",
        ),
        on_mount=[State.on_load, State.load_reports],
        size="4",
    )
