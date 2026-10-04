"""HTML-based Reflex components preserve the original CSS and semantics."""

import json
import os
from urllib.parse import urlsplit

import reflex as rx
from reflex_components_core.react_router.dom import ReactRouterLink


def attrs(**values):
    return {
        "data-" + key.replace("_", "-"): str(value) for key, value in values.items()
    }


def icon(name, size=18, **props):
    return rx.icon(name, size=size, **props)


def link(*children, href, **props):
    """Document navigation initializes browser-local interactions on every page."""
    return ReactRouterLink.create(*children, href=href, reload_document=True, **props)


def button(*children, action=None, variant="primary", class_name="", **props):
    if action:
        props["custom_attrs"] = {
            **props.get("custom_attrs", {}),
            **attrs(action=action),
        }
    return rx.el.button(
        *children,
        type=props.pop("type", "button"),
        class_name=f"btn {variant} {class_name}",
        **props,
    )


def link_button(text, href):
    return link(text, icon("arrow-right", 15), href=href, class_name="text-link")


def avatar(alias="J", color="blue", small=False):
    return rx.el.span(
        alias[:1],
        class_name=f"avatar {color}{' small' if small else ''}",
        custom_attrs={"aria-hidden": "true"},
    )


def brand():
    return rx.el.span(
        rx.el.span(rx.el.i(), rx.el.i(), class_name="brand-mark"),
        "Intersect",
        rx.el.span(".", class_name="brand-dot"),
        class_name="brand",
    )


def card(*children, class_name="", **props):
    return rx.el.section(*children, class_name=f"card {class_name}", **props)


def page_title(title, subtitle):
    return rx.el.div(rx.el.h1(title), rx.el.p(subtitle), class_name="page-title")


def privacy_note():
    return rx.el.span(
        icon("lock-keyhole", 13),
        "Anonymous until you both choose otherwise",
        class_name="privacy-note",
    )


def conversation_art():
    return rx.el.div(
        rx.el.span(class_name="art-orbit"),
        rx.el.span(class_name="art-loop"),
        *[
            rx.el.span(
                rx.el.i(), rx.el.i(), rx.el.i(), class_name=f"art-bubble {color}"
            )
            for color in ["white", "blue"]
        ],
        rx.el.span("✧", class_name="art-spark"),
        class_name="conversation-art",
        custom_attrs={"aria-hidden": "true"},
    )


def demo_script():
    return rx.fragment(api_config(), rx.script(src="/demo.js"))


def api_config():
    cloud_api_base_url = "https://3aacb1ae-3cd2-44eb-b2f9-933a8360f096.fly.dev"
    configured_api_base_url = os.getenv("INTERSECT_API_URL", "").strip().rstrip("/")
    parsed_api_base_url = urlsplit(configured_api_base_url)
    api_base_url = (
        configured_api_base_url
        if parsed_api_base_url.scheme == "https"
        and parsed_api_base_url.hostname
        and parsed_api_base_url.hostname not in {"localhost", "127.0.0.1", "::1"}
        else cloud_api_base_url
    )
    return rx.script(
        "window.intersectApiBaseURL = "
        + json.dumps(api_base_url)
        + ";"
    )


def overlays():
    return rx.fragment(
        rx.el.div(
            rx.el.span("Loading…", id="data-status-message"),
            button(
                "Try again",
                action="retry-load",
                id="retry-load",
                hidden=True,
                variant="secondary",
            ),
            id="data-status",
            class_name="data-status",
            role="status",
        ),
        rx.el.dialog(
            rx.el.div(
                rx.el.button(
                    icon("x", 20),
                    class_name="icon-button modal-close",
                    type="button",
                    custom_attrs={
                        **attrs(action="close-modal"),
                        "aria-label": "Close dialog",
                    },
                ),
                rx.el.h2(id="modal-title"),
                rx.el.div(id="modal-body"),
                class_name="modal-content",
            ),
            id="demo-modal",
            class_name="modal",
            custom_attrs={"aria-labelledby": "modal-title"},
        ),
        rx.el.div(id="demo-toast", class_name="toast", role="status", hidden=True),
        demo_script(),
    )
