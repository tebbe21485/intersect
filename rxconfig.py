import reflex as rx

config = rx.Config(
    app_name="mule_hacks",
    plugins=[
        rx.plugins.SitemapPlugin(),
    ],
    disable_plugins=[rx.plugins.TailwindV4Plugin, rx.plugins.RadixThemesPlugin],
)
