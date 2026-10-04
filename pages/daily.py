import reflex as rx

from ..components.activities import daily_card
from ..components.layout import shell
from ..components.ui import avatar, button, card, icon, page_title


def daily():
    return shell(
        "daily",
        page_title(
            "A small question. A world of perspectives.",
            "Share a little of what makes you, you.",
        ),
        daily_card(expanded=True),
        rx.el.section(
            rx.el.div(
                rx.el.h2("A few different perspectives"),
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
        ),
    )
