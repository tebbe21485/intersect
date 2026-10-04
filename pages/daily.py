import reflex as rx

from ..components.layout import shell
from ..components.ui import avatar, button, card, icon, link


def daily():
    return shell(
        "daily",
        link(
            icon("arrow-left", 16),
            "Go back",
            href="/",
            class_name="btn secondary daily-back",
        ),
        card(
            rx.el.span("Daily question", class_name="section-label"),
            rx.el.h2("Loading question...", id="daily-detail-question"),
            class_name="daily-card question-detail",
        ),
        rx.el.section(
            rx.el.div(
                rx.el.h2("A few different perspectives", id="daily-perspectives-title"),
                rx.el.span("Always anonymous", class_name="muted text-sm"),
                class_name="section-heading",
            ),
            card(
                avatar("You"),
                rx.el.div(
                    rx.el.strong("You"),
                    rx.el.p(id="your-answer"),
                    rx.el.span(
                        "Your answer has been shared anonymously",
                        class_name="muted text-xs",
                    ),
                ),
                button(
                    "Find a similar answer",
                    icon("arrow-right", 16),
                    action="similar-answer",
                    variant="secondary",
                ),
                id="your-answer-card",
                hidden=True,
                class_name="answer-card",
            ),
            rx.el.div(
                rx.el.p("Loading responses…", class_name="muted"), id="daily-responses"
            ),
            class_name="mt-8",
            id="daily-perspectives",
        ),
    )
