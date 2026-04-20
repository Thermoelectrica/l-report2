"""Login page component."""

import reflex as rx
from report2.auth.auth_state import AuthState


def login_page() -> rx.Component:
    """Login page with username/password form."""
    return rx.center(
        rx.card(
            rx.vstack(
                rx.heading(
                    "Report Generator",
                    size="8",
                    weight="bold",
                    text_align="center",
                ),
                rx.text(
                    "Sign in to continue",
                    size="3",
                    color_scheme="gray",
                    text_align="center",
                ),
                rx.divider(),
                rx.form(
                    rx.vstack(
                        rx.vstack(
                            rx.text(
                                "Username",
                                size="2",
                                weight="medium",
                                color_scheme="gray",
                            ),
                            rx.input(
                                placeholder="Enter your username",
                                name="username",
                                type="text",
                                size="3",
                                width="100%",
                                required=True,
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        rx.vstack(
                            rx.text(
                                "Password",
                                size="2",
                                weight="medium",
                                color_scheme="gray",
                            ),
                            rx.input(
                                placeholder="Enter your password",
                                name="password",
                                type="password",
                                size="3",
                                width="100%",
                                required=True,
                            ),
                            width="100%",
                            spacing="1",
                        ),
                        rx.cond(
                            AuthState.login_error,
                            rx.callout(
                                AuthState.login_error,
                                icon="triangle_alert",
                                color_scheme="red",
                                size="2",
                                width="100%",
                            ),
                        ),
                        rx.button(
                            rx.cond(
                                AuthState.is_logging_in,
                                rx.hstack(
                                    rx.spinner(size="2"),
                                    rx.text("Signing in..."),
                                    spacing="2",
                                ),
                                rx.text("Sign In"),
                            ),
                            type="submit",
                            size="3",
                            width="100%",
                            disabled=AuthState.is_logging_in,
                        ),
                        spacing="4",
                        width="100%",
                    ),
                    on_submit=AuthState.login,
                    width="100%",
                ),
                spacing="5",
                width="100%",
            ),
            size="4",
            max_width="400px",
        ),
        height="100vh",
        width="100%",
        background="var(--gray-2)",
    )
