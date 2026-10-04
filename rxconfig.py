import os

import reflex as rx

# Reflex's dev watcher includes data/ and does not ignore .sqlite3 journals.
# Database writes must not restart the backend or reinstall frontend packages.
# Relative paths avoid the colon-delimited setting splitting Windows drive names.
os.environ.setdefault(
    "REFLEX_HOT_RELOAD_OVERRIDE_PATHS", "mule_hacks:rxconfig.py:assets"
)

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
