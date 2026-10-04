import os

import reflex as rx

config = rx.Config(
    app_name="mule_hacks",
    cors_allowed_origins=[
        origin.strip().rstrip("/")
        for origin in os.getenv("INTERSECT_ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ],
    plugins=[
        rx.plugins.SitemapPlugin(),
    ],
    disable_plugins=[rx.plugins.TailwindV4Plugin, rx.plugins.RadixThemesPlugin],
)
