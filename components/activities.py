import reflex as rx

from .ui import (
    attrs,
    button,
    card,
    conversation_art,
    icon,
)


def daily_card(expanded=False):
    return rx.el.div(
        card(
            rx.el.div(
                rx.el.span(
                    icon("message-circle", 16), "Daily question", class_name="section-label"
                ),
                rx.el.h2("Loading today’s question…", id="daily-question-title"),
                rx.el.form(
                    rx.el.label(
                        "Your anonymous answer",
                        html_for="daily-response",
                        class_name="sr-only",
                    ),
                    rx.el.textarea(
                        id="daily-response",
                        name="answer",
                        required=True,
                        max_length=500,
                        placeholder="The little things count. What’s yours?",
                    ),
                    rx.el.div(
                        button(
                            icon("send", 15),
                            rx.el.span("Share anonymously", id="daily-submit-label"),
                            type="submit",
                        ),
                        button(
                            "Explore responses",
                            icon("arrow-right", 15),
                            action="explore-responses",
                            variant="secondary",
                            id="daily-explore",
                        ),
                        class_name="daily-actions",
                    ),
                    on_submit=None,
                    id="daily-form",
                    custom_attrs=attrs(form="daily"),
                ),
                class_name="daily-content relative z-10",
            ),
            conversation_art(),
        ),
        id="daily-cards",
        class_name="activity-stack",
    )



def poll_card():
    return rx.el.div(
        card(
            rx.el.span("Quick poll", class_name="section-label"),
            rx.el.h3("Loading the poll…", id="poll-title"),
            rx.el.div(
                id="poll-options",
                class_name="poll-options",
            ),
            rx.el.div(
                rx.el.span(
                    "One choice. A little common ground.",
                    id="poll-note",
                    class_name="muted text-xs",
                ),
                rx.el.button(
                    "Find your match",
                    icon("arrow-right", 15),
                    type="button",
                    class_name="text-link",
                    id="poll-match",
                    hidden=True,
                    custom_attrs=attrs(action="poll-match"),
                ),
                class_name="poll-footer",
            ),
            class_name="poll-card",
        ),
        id="poll-cards",
        class_name="activity-stack",
    )
