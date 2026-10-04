import reflex as rx

from ..components.layout import shell
from ..components.ui import icon, page_title


def groups():
    return shell(
        "groups",
        page_title(
            "Small circles. Shared interests.",
            "Find a space where the conversation comes naturally.",
        ),
        rx.el.div(
            rx.el.p("Loading groups…", class_name="muted"),
            id="groups-grid",
            class_name="groups-grid",
        ),
        rx.el.div(
            icon("compass", 24),
            rx.el.div(
                rx.el.h3("There’s room for you here."),
                rx.el.p(
                    "Join a discussion, ask a question, or just start by listening. Your identity stays yours."
                ),
            ),
            class_name="group-guidance",
        ),
    )
