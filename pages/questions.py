import reflex as rx

from ..components.layout import shell
from ..components.ui import button, icon, page_title


def questions():
    return shell(
        "questions",
        rx.el.div(
            page_title(
                "A question can open a door.",
                "Ask freely. Share a little wisdom. Find a new perspective.",
            ),
            button("Ask a question", icon("arrow-right", 16), action="post-question"),
            class_name="question-heading flex justify-between items-start gap-4",
        ),
        rx.el.div(id="question-filters", class_name="filter-tabs"),
        rx.el.div(
            rx.el.p("Loading questions…", class_name="muted"),
            id="question-list",
            class_name="question-list",
        ),
    )
