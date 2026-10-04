import reflex as rx

from ..data import NAV
from .ui import attrs, avatar, brand, icon, link, overlays


def navigation(page, mobile=False):
    return rx.el.nav(
        *[
            link(
                icon(symbol, 20),
                rx.el.span(label),
                *(
                    [
                        rx.el.span(
                            "…",
                            class_name="nav-count",
                            custom_attrs=attrs(connection_count="true"),
                        )
                    ]
                    if key == "messages" and not mobile
                    else []
                ),
                href=href,
                class_name=("active" if page == key else "")
                if mobile
                else f"nav-item {'active' if page == key else ''}",
                custom_attrs={"aria-current": "page"} if page == key else {},
            )
            for key, href, label, symbol in NAV
        ],
        class_name="bottom-nav" if mobile else "",
        custom_attrs={
            "aria-label": "Mobile navigation" if mobile else "Main navigation"
        },
    )


def sidebar(page):
    return rx.el.aside(
        link(
            brand(),
            href="/",
            class_name="brand-button",
            custom_attrs={"aria-label": "Intersect home"},
        ),
        navigation(page),
        class_name="sidebar",
    )


def shell(page, *content):
    return rx.el.div(
        sidebar("home" if page == "daily" else page),
        rx.el.div(
            rx.el.header(
                link(brand(), href="/", class_name="mobile-brand"),
                rx.el.span(class_name="topbar-context"),
                rx.el.button(
                    avatar(small=True),
                    type="button",
                    class_name="profile-button",
                    custom_attrs={
                        **attrs(action="profile"),
                        "aria-label": "Your profile",
                    },
                ),
                class_name="topbar",
            ),
            rx.el.main(*content, class_name="main-content"),
            class_name="workspace",
        ),
        navigation("home" if page == "daily" else page, mobile=True),
        overlays(),
        class_name="app-shell",
        custom_attrs=attrs(page=page),
    )
