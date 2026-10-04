"""Intersect frontend: modular Reflex pages with browser-local demo interactions."""

import reflex as rx

from .pages.connect import connect
from .pages.daily import daily
from .pages.groups import groups
from .pages.home import home
from .pages.messages import messages
from .pages.questions import questions
from .pages.welcome import welcome

app = rx.App(
    enable_state=False,
    theme=None,
    stylesheets=[
        "/css/theme.css",
        "/css/utilities.css",
        "/css/base.css",
        "/css/readability.css",
        "/css/messaging.css",
        "/css/reflex.css",
    ],
)
for route, page in [
    ("/", home),
    ("/daily", daily),
    ("/connect", connect),
    ("/groups", groups),
    ("/questions", questions),
    ("/messages", messages),
    ("/welcome", welcome),
]:
    app.add_page(page, route=route, title="Intersect · People first. Names later.")
