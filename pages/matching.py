"""Matching inputs and mode selection, kept separate from account identity."""

import reflex as rx

from ..components.layout import shell
from ..components.puzzle import puzzle_widget
from ..components.ui import button, card, page_title


def matching():
    return shell(
        "matching",
        page_title(
            "Build your puzzle.",
            "Add your pieces, answer optional questions, then explore connections.",
        ),
        rx.el.p(
            id="matching-status",
            role="status",
            class_name="form-feedback",
            custom_attrs={"aria-live": "polite"},
        ),
        rx.el.div(
            *[
                rx.el.button(
                    label,
                    type="button",
                    role="tab",
                    id=f"matching-tab-{key}",
                    tab_index=0 if key == "puzzle" else -1,
                    custom_attrs={
                        "data-matching-tab": key,
                        "aria-selected": "true" if key == "puzzle" else "false",
                        "aria-controls": f"matching-panel-{key}",
                    },
                )
                for key, label in [("puzzle", "Puzzle"), ("personal", "Personal answers"), ("connections", "Connections")]
            ],
            role="tablist",
            class_name="module-tabs matching-tabs",
            custom_attrs={"aria-label": "Puzzle builder sections"},
        ),
        rx.el.div(
            card(
                rx.el.h2("Your puzzle"),
                rx.el.p(
                    "Create 4–8 pieces. Titles appear on your puzzle; click a piece to read its description.",
                    class_name="muted",
                ),
                rx.el.p(id="puzzle-piece-count", role="status", custom_attrs={"aria-live": "polite"}),
                puzzle_widget(mode="preview"),
                rx.el.div(id="matching-pieces"),
                rx.el.form(
                    rx.el.input(name="id", type="hidden"),
                    rx.el.label(
                        "Category",
                        rx.el.select(
                            name="category", id="puzzle-category", required=True
                        ),
                    ),
                    rx.el.label(
                        "Title",
                        rx.el.input(
                            name="title", required=True, max_length=20,
                            placeholder="e.g. Robotics",
                        ),
                    ),
                    rx.el.label(
                        "Description",
                        rx.el.textarea(
                            name="description",
                            required=True,
                            max_length=500,
                            placeholder="I enjoy building robots and learning how they work.",
                        ),
                    ),
                    rx.el.div(
                        button("Save piece", type="submit", disabled=True),
                        button(
                            "Cancel edit",
                            variant="secondary",
                            id="cancel-piece-edit",
                            hidden=True,
                        ),
                        class_name="daily-actions",
                    ),
                    id="puzzle-editor",
                    method="post",
                    class_name="form-stack",
                ),
                button("Continue to connections", id="puzzle-continue", disabled=True),
                class_name="matching-card",
                id="matching-panel-puzzle",
                role="tabpanel",
                custom_attrs={"aria-labelledby": "matching-tab-puzzle"},
            ),
            card(
                rx.el.h2("Personal answers"),
                rx.el.p(
                    "These are optional. Missing answers are left out of the score. Your name and contact details are separate.",
                    class_name="muted",
                ),
                rx.el.form(
                    rx.el.div(id="personal-fields"),
                    button("Save answers", type="submit", disabled=True),
                    id="personal-editor",
                    method="post",
                    class_name="form-stack",
                ),
                class_name="matching-card",
                id="matching-panel-personal",
                role="tabpanel",
                hidden=True,
                custom_attrs={"aria-labelledby": "matching-tab-personal"},
            ),
            class_name="matching-inputs",
        ),
        card(
            rx.el.h2("What kind of connection?"),
            rx.el.form(
                rx.el.label(
                    "Connection mode",
                    rx.el.select(
                        rx.el.option("Similar", value="similar"),
                        rx.el.option(
                            "Different, with common ground", value="different"
                        ),
                        rx.el.option("A specific trait", value="trait"),
                        id="matching-mode",
                        name="mode",
                    ),
                ),
                rx.el.label(
                    "Choose a saved trait",
                    rx.el.select(id="matching-trait", name="trait"),
                    id="matching-trait-label",
                    hidden=True,
                ),
                button("Find connections", type="submit", disabled=True),
                id="matching-search",
                method="post",
                class_name="form-stack",
            ),
            rx.el.div(id="matching-results", class_name="matching-results"),
            class_name="matching-card",
            id="matching-panel-connections",
            role="tabpanel",
            hidden=True,
            custom_attrs={"aria-labelledby": "matching-tab-connections"},
        ),
        rx.script(src="/matching.js"),
    )
