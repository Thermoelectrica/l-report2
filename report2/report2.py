"""Welcome to Reflex! This file outlines the steps to create a basic app."""

import reflex as rx

from rxconfig import config


class State(rx.State):
    val: int = 0
    """The app state."""

    @rx.event
    def setval(self):
        self.val += 1


def index() -> rx.Component:
    # Welcome Page (Index)
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Welcome to Reflex!", size="9"),
            rx.text(f"val = {State.val}"),
            rx.button("Increase val", on_click=State.setval),
            spacing="5",
            justify="center",
            min_height="85vh",
        ),
        on_mount=State.setval
    )


app = rx.App()
app.add_page(index)
