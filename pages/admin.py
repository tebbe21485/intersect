import reflex as rx

from ..components.ui import api_config, attrs, icon, link, overlays, page_title


def admin():
    # Authentication and authorization are enforced by every admin API operation.
    return rx.el.div(
        rx.el.aside(
            link(icon("arrow-left", 20), "Back to Intersect", href="/", class_name="sidebar-back"),
            rx.el.div(rx.el.h1("Admin portal"), class_name="conversation-list-heading"),
            rx.el.p("Choose what you want to manage.", class_name="conversation-list-intro"),
            rx.el.nav(id="admin-navigation", hidden=True, custom_attrs={"aria-label": "Community management"}),
            class_name="sidebar admin-sidebar",
        ),
        rx.el.div(
            rx.el.main(
                page_title("Manage the community.", "Questions, polls, groups and reports."),
                rx.el.p("Checking administrator access?", id="admin-status", role="status"),
                rx.el.div(id="admin-content", hidden=True),
                class_name="main-content admin-page",
            ),
            class_name="workspace",
        ),
        overlays(),
        api_config(),
        rx.script(src="/admin.js"),
        class_name="app-shell admin-mode",
        custom_attrs=attrs(page="admin"),
    )
