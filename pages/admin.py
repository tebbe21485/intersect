import reflex as rx

from ..components.layout import shell
from ..components.ui import api_config, page_title


def admin():
    # Authentication and authorization are enforced by every admin API operation.
    return rx.el.div(
        shell(
            "admin",
            page_title(
                "Manage the community.", "Questions, polls, groups and reports."
            ),
            rx.el.p("Checking administrator access…", id="admin-status", role="status"),
            rx.el.div(id="admin-content", hidden=True),
        ),
        api_config(),
        rx.script(src="/admin.js"),
    )
