import reflex as rx

from .ui import (
    attrs,
    button,
    card,
    conversation_art,
    icon,
    link,
    link_button,
    privacy_note,
)


def daily_card(expanded=False):
    return card(
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
                button(
                    icon("send", 15),
                    rx.el.span("Share anonymously", id="daily-submit-label"),
                    type="submit",
                ),
                on_submit=None,
                id="daily-form",
                custom_attrs=attrs(form="daily"),
            ),
            rx.el.p(id="submitted-answer", class_name="submitted-answer", hidden=True),
            class_name="daily-content relative z-10",
        ),
        conversation_art(),
        rx.el.div(
            privacy_note(),
            rx.el.span("A new question. Every day.")
            if expanded
            else link_button("Explore responses", "/daily"),
            class_name="daily-footer",
        ),
        class_name=f"daily-card {'expanded' if expanded else ''}",
    )


def poll_card():
    return card(
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
    )


def challenge_card():
    return card(
        rx.el.span(icon("sparkles", 16), "Daily challenge", class_name="section-label"),
        rx.el.h2("Let curiosity lead.", id="challenge-title"),
        rx.el.p(
            "Start a conversation with someone whose answer surprised you.",
            id="challenge-description",
        ),
        rx.el.div(
            rx.el.div(rx.el.span(id="challenge-progress"), class_name="progress-track"),
            rx.el.span("0 of 1", id="challenge-count"),
            class_name="progress-row",
        ),
        link(
            "Explore responses",
            icon("arrow-right", 16),
            href="/daily",
            class_name="btn white",
        ),
        class_name="challenge-card",
    )
