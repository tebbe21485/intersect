import reflex as rx

from ..components.ui import brand, conversation_art, demo_script, icon, link


def welcome():
    return rx.el.div(
        rx.el.header(
            brand(),
            rx.el.span(
                "A little common ground goes a long way.", class_name="muted text-sm"
            ),
        ),
        rx.el.main(
            rx.el.div(
                rx.el.h1("People first.", rx.el.br(), "Names later."),
                rx.el.p("Connect through conversation before identity."),
                rx.el.p(
                    "A shared answer. A little curiosity. Someone you might never have met otherwise.",
                    class_name="muted",
                ),
                link(
                    "Sign in",
                    icon("arrow-right", 18),
                    href="/login",
                    class_name="btn primary",
                ),
                rx.el.span(
                    icon("lock-keyhole", 14),
                    "Your identity stays private until you choose to share it",
                    class_name="welcome-note",
                ),
                class_name="welcome-copy",
            ),
            rx.el.div(
                conversation_art(),
                rx.el.div(
                    "“Turns out, we have more",
                    rx.el.br(),
                    "in common than we thought.”",
                    class_name="welcome-quote",
                ),
                class_name="welcome-art",
            ),
        ),
        rx.el.footer(
            rx.el.span("Prompt"),
            icon("arrow-right", 15),
            rx.el.span("Common ground"),
            icon("arrow-right", 15),
            rx.el.span("Conversation"),
            icon("arrow-right", 15),
            rx.el.span("Connection"),
        ),
        demo_script(),
        class_name="welcome",
        custom_attrs={"data-page": "welcome"},
    )
