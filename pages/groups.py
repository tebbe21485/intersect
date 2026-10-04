import reflex as rx

from ..components.layout import shell
from ..components.ui import button, icon, page_title


def groups():
    return shell(
        "groups",
        rx.el.div(
            page_title(
                "Small circles. Shared interests.",
                "Find a space where the conversation comes naturally.",
            ),
            button("Create a group/thread", action="propose-group", class_name="mb-6"),
            rx.el.div(id="group-proposals", class_name="group-proposals"),
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
            id="groups-browse",
        ),
        rx.el.section(
            id="group-chat-content",
            class_name="group-chat-content",
            hidden=True,
            custom_attrs={"aria-label": "Group thread"},
        ),
    )
