"""Modular Reflex pages with a same-origin Python/SQLite application API."""

import asyncio
from pathlib import Path

import reflex as rx

from .backend.api import create_api
from .backend.sqlite import SQLiteSettings
from .db_handler import init_db
from .pages.accounts import login, profile, register
from .pages.admin import admin
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
    api_transformer=create_api(),
    stylesheets=[
        "/css/theme.css",
        "/css/utilities.css",
        "/css/base.css",
        "/css/readability.css",
        "/css/messaging.css",
        "/css/reflex.css",
        "/css/backend.css",
    ],
)


async def initialize_database():
    settings = SQLiteSettings.from_environment()
    if str(settings.path) != ":memory:" and not Path(settings.path).exists():
        await asyncio.to_thread(init_db, settings)


app.register_lifespan_task(initialize_database)

for route, page in [
    ("/", home),
    ("/daily", daily),
    ("/connect", connect),
    ("/groups", groups),
    ("/questions", questions),
    ("/messages", messages),
    ("/welcome", welcome),
    ("/login", login),
    ("/register", register),
    ("/profile", profile),
    ("/admin", admin),
]:
    app.add_page(page, route=route, title="Intersect · People first. Names later.")
