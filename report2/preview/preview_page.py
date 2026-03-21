import reflex as rx

from report2.preview.preview_state import PreviewState


def preview_page() -> rx.Component:
    """Preview page showing report parameters and HTML preview."""
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            # Two-column layout
            rx.cond(
                PreviewState.is_loading,
                # Loading state
                rx.center(
                    rx.vstack(
                        rx.spinner(size="3"),
                        rx.text("Generating preview...", size="3"),
                        spacing="3",
                    ),
                    height="60vh",
                ),
                # Content
                rx.cond(
                    PreviewState.error_message != "",
                    # Error state
                    rx.callout(
                        PreviewState.error_message,
                        icon="badge_alert",
                        color_scheme="red",
                        width="100%",
                    ),
                    # Preview content
                    rx.hstack(
                        # Left column - Back button outside card, then card with report name and parameters
                        rx.vstack(
                            # Back button (outside card, full width)
                            rx.link(
                                rx.button(
                                    rx.icon("arrow-left"),
                                    "Back to Reports",
                                    variant="soft",
                                    width="100%",
                                ),
                                href="/",
                                width="100%",
                            ),
                            # Card with report name and parameters
                            rx.box(
                                rx.vstack(
                                    # Report name (left-aligned)
                                    rx.heading(
                                        PreviewState.report_name,
                                        size="5",
                                        text_align="left",
                                    ),
                                    rx.divider(),
                                    # Parameters list (no heading)
                                    rx.cond(
                                        PreviewState.parameters_dict,
                                        rx.vstack(
                                            rx.foreach(
                                                PreviewState.parameters_dict.items(),
                                                lambda item: rx.box(
                                                    rx.vstack(
                                                        rx.text(
                                                            item[0],
                                                            size="2",
                                                            weight="bold",
                                                            color="gray",
                                                        ),
                                                        rx.text(
                                                            item[1],
                                                            size="2",
                                                        ),
                                                        spacing="1",
                                                        align_items="start",
                                                    ),
                                                    padding="8px",
                                                    border_radius="6px",
                                                    background="var(--gray-2)",
                                                    width="100%",
                                                ),
                                            ),
                                            spacing="2",
                                            width="100%",
                                        ),
                                        rx.text("No parameters", size="2", color="gray"),
                                    ),
                                    spacing="3",
                                    align_items="start",
                                    width="100%",
                                ),
                                padding="20px",
                                border_radius="12px",
                                border="1px solid var(--gray-5)",
                                background="var(--gray-1)",
                            ),
                            spacing="3",
                            width="25%",
                        ),
                        # Right column - HTML Preview (direct, no card)
                        rx.box(
                            rx.html(PreviewState.preview_html),
                            width="75%",
                            border="1px solid var(--gray-5)",
                            border_radius="8px",
                            padding="16px",
                            background="white",
                        ),
                        spacing="4",
                        width="100%",
                        align_items="start",
                    ),
                ),
            ),
            spacing="4",
            width="100%",
            padding="20px",
        ),
        on_mount=PreviewState.load_preview,
        size="4",
    )
