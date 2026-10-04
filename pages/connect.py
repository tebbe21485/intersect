import reflex as rx

from ..components.layout import shell
from ..components.ui import page_title


def connect():
    return shell(
        "connect",
        page_title(
            "Common ground. New connections.",
            "You know what you share. Get to know the person behind it.",
        ),
        rx.el.div(
            rx.el.p("Loading connections…", class_name="muted"),
            class_name="connections-grid",
            id="connections-grid",
        ),
    )
