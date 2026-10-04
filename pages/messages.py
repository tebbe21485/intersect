import reflex as rx

from ..components.ui import attrs, card, icon, link, overlays


def messages():
    return rx.el.div(
        rx.el.aside(
            link(
                icon("arrow-left", 20),
                "Back to Intersect",
                href="/",
                class_name="sidebar-back",
            ),
            rx.el.div(
                rx.el.h1("Messages"),
                rx.el.span(
                    "…",
                    class_name="count",
                    custom_attrs=attrs(connection_count="true"),
                ),
                class_name="conversation-list-heading",
            ),
            rx.el.p(
                "A little common ground. Your people.",
                class_name="conversation-list-intro",
            ),
            rx.el.nav(
                rx.el.p("Loading conversations…", class_name="muted"),
                class_name="conversation-list",
                id="conversation-list",
                custom_attrs={"aria-label": "Your conversations"},
            ),
            rx.el.p(
                icon("lock-keyhole", 16),
                "Your identity stays yours until you both agree.",
                class_name="conversation-sidebar-note",
            ),
            class_name="sidebar conversations-sidebar",
            custom_attrs={"aria-label": "Conversations"},
        ),
        rx.el.div(
            rx.el.main(
                rx.el.div(
                    card(
                        rx.el.div(id="chat-content"),
                        class_name="chat-card",
                        id="chat-card",
                    ),
                    class_name="messaging-layout",
                ),
                class_name="main-content messages-page",
            ),
            class_name="workspace",
        ),
        overlays(),
        class_name="app-shell messaging-mode",
        custom_attrs=attrs(page="messages"),
    )
