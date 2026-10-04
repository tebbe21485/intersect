import reflex as rx

from ..components.activities import challenge_card, daily_card, poll_card
from ..components.layout import shell
from ..components.ui import attrs, icon, link, page_title


def home():
    return shell(
        "home",
        page_title(
            "A little curiosity. A real connection.",
            "Good conversations start with something in common.",
        ),
        rx.el.div(
            *[
                rx.el.button(
                    label,
                    type="button",
                    id=f"activity-{key}",
                    role="tab",
                    tab_index=0 if key == "daily" else -1,
                    custom_attrs={
                        **attrs(action="activity", activity=key),
                        "aria-selected": str(key == "daily").lower(),
                        "aria-controls": f"panel-{key}",
                    },
                )
                for key, label in [
                    ("daily", "Daily question"),
                    ("poll", "Mini poll"),
                    ("challenge", "Challenge"),
                ]
            ],
            class_name="activity-tabs",
            role="tablist",
            custom_attrs={"aria-label": "Today's activities"},
        ),
        *[
            rx.el.div(
                component,
                id=f"panel-{key}",
                class_name="activity-panel",
                role="tabpanel",
                hidden=key != "daily",
                custom_attrs={"aria-labelledby": f"activity-{key}"},
            )
            for key, component in [
                ("daily", daily_card()),
                ("poll", poll_card()),
                ("challenge", challenge_card()),
            ]
        ],
        rx.el.section(
            rx.el.h2("Follow your curiosity", id="directory-heading"),
            *[
                link(
                    icon(symbol, 30, class_name="destination-icon"),
                    rx.el.span(rx.el.strong(title), rx.el.span(description)),
                    icon("chevron-right", 22),
                    href=href,
                    class_name="destination-row",
                )
                for href, title, description, symbol in [
                    (
                        "/connect",
                        "Your connections",
                        "Keep getting to know your common ground.",
                        "users",
                    ),
                    (
                        "/groups",
                        "Small interest groups",
                        "Find a conversation around what you love.",
                        "messages-square",
                    ),
                    (
                        "/questions",
                        "Question board",
                        "Ask freely. Share a new perspective.",
                        "circle-help",
                    ),
                ]
            ],
            class_name="discovery-directory",
            custom_attrs={"aria-labelledby": "directory-heading"},
        ),
    )
