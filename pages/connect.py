import reflex as rx

from ..components.layout import shell
from ..components.ui import link, page_title


def connect():
    return shell(
        "connect",
        page_title(
            "Common ground. New connections.",
            "You know what you share. Get to know the person behind it.",
        ),
        link(
            "Build your puzzle",
            href="/matching",
            class_name="btn primary daily-back",
        ),
        rx.el.div(
            rx.el.p("Loading connections…", class_name="muted"),
            class_name="connections-grid",
            id="connections-grid",
        ),
    )
