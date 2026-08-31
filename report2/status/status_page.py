"""Status page for debugging and monitoring."""

import reflex as rx

from report2.status.status_state import StatusState


def config_item(item: list) -> rx.Component:
    """Render a single config key-value pair."""
    return rx.hstack(
        rx.text(
            f"{item[0]}:",
            weight="bold",
            size="2",
            width="250px",
        ),
        rx.text(
            item[1],
            size="2",
            color="gray",
            word_break="break-all",
        ),
        spacing="2",
        align_items="start",
    )


def config_section(section: list) -> rx.Component:
    """Render a configuration section. Section is [section_name, section_data]."""
    return rx.box(
        rx.vstack(
            rx.heading(section[0], size="4", color="blue"),
            rx.divider(),
            rx.foreach(
                section[1],
                lambda item: rx.fragment(
                    config_item(item),
                    key=item[0],
                ),
            ),
            spacing="2",
            align_items="start",
            width="100%",
        ),
        padding="16px",
        border_radius="8px",
        border="1px solid var(--gray-5)",
        background="var(--gray-1)",
        width="100%",
    )


def report_name_item(report_name: str) -> rx.Component:
    """Render a single report name."""
    return rx.hstack(
        rx.icon("folder", size=16, color="blue"),
        rx.text(
            report_name,
            size="2",
            weight="medium",
        ),
        spacing="2",
        align_items="center",
        padding="8px",
        border_radius="6px",
        background="var(--gray-2)",
    )


def status_page() -> rx.Component:
    """Status page showing configuration and reports structure."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            # Header
            rx.hstack(
                rx.vstack(
                    rx.heading("Application Status", size="8"),
                    rx.text(
                        "Configuration and debug information",
                        size="3",
                        color="gray",
                    ),
                    spacing="1",
                    align_items="start",
                ),
                rx.spacer(),
                rx.link(
                    rx.button(
                        rx.icon("home"),
                        "Back to Home",
                        variant="soft",
                        size="2",
                    ),
                    href="/",
                ),
                width="100%",
                align_items="center",
            ),
            rx.divider(),
            
            # Configuration Section
            rx.vstack(
                rx.heading("Configuration Variables", size="6"),
                rx.cond(
                    StatusState.config_error != "",
                    rx.callout(
                        StatusState.config_error,
                        icon="alert-triangle",
                        color_scheme="red",
                    ),
                    rx.vstack(
                        rx.foreach(
                            StatusState.config_data,
                            config_section,
                        ),
                        spacing="3",
                        width="100%",
                    ),
                ),
                spacing="3",
                align_items="start",
                width="100%",
            ),
            
            rx.divider(),
            
            # Reports List Section
            rx.vstack(
                rx.heading("Available Reports", size="6"),
                rx.cond(
                    StatusState.reports_error != "",
                    rx.callout(
                        StatusState.reports_error,
                        icon="alert-triangle",
                        color_scheme="red",
                    ),
                    rx.cond(
                        StatusState.report_names,
                        rx.vstack(
                            rx.foreach(
                                StatusState.report_names,
                                report_name_item,
                            ),
                            spacing="2",
                            width="100%",
                        ),
                        rx.text(
                            "No reports found",
                            size="2",
                            color="gray",
                        ),
                    ),
                ),
                spacing="3",
                align_items="start",
                width="100%",
            ),
            
            spacing="5",
            width="100%",
            padding="20px",
        ),
        on_mount=[StatusState.on_load],
        size="4",
    )
