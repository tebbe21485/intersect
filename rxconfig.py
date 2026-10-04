import os
import reflex as rx

# Check if we are running in the native Reflex Cloud environment
IS_REFLEX_CLOUD = os.getenv("REFLEX_CLOUD") == "true" or "REFLEX_APP_ID" in os.environ

# 1. Parse your custom origins if they exist
custom_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("INTERSECT_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

# 2. Build the final allowed origins list
# If in Reflex Cloud, we must NOT override with an empty list, otherwise it blocks the app.
if IS_REFLEX_CLOUD:
    # Let Reflex Cloud handle defaults automatically, or append custom ones if provided
    cors_origins = custom_origins if custom_origins else ["*"]
else:
    cors_origins = custom_origins

config = rx.Config(
    app_name="mule_hacks",
    # Leave api_url out entirely when using native 'reflex deploy'! 
    # The platform dynamically links them.
    cors_allowed_origins=cors_origins,
    plugins=[
        rx.plugins.SitemapPlugin(),
    ],
    disable_plugins=[rx.plugins.TailwindV4Plugin, rx.plugins.RadixThemesPlugin],
)
