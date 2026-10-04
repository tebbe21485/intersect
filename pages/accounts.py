"""Account pages using the existing Intersect component and styling vocabulary."""

import reflex as rx

from ..components.puzzle import puzzle_widget
from ..components.ui import api_config, attrs, brand, button, card, link


def field(label, name, kind="text", required=True, maximum=128):
    return rx.el.label(
        label,
        rx.el.input(
            name=name,
            type=kind,
            required=required,
            max_length=maximum,
            auto_complete={
                "email": "email",
                "password": "current-password",
                "firstName": "given-name",
                "lastName": "family-name",
                "phone": "tel",
            }.get(name, "off"),
        ),
    )


def account_page(mode):
    registering = mode == "register"
    editing = mode == "profile"
    title = (
        "Your profile"
        if editing
        else ("A little introduction." if registering else "Welcome back.")
    )
    return rx.el.main(
        link(brand(), href="/", class_name="brand-button"),
        card(
            rx.el.h1(title),
            rx.el.p(
                "Names stay private. Conversations start with your alias."
                if registering or editing
                else "Sign in to continue the conversation.",
                class_name="muted",
            ),
            rx.el.form(
                *(
                    [
                        field("First name", "firstName", maximum=80),
                        field("Last name", "lastName", maximum=80),
                        field("LinkedIn (optional)", "linkedin", "url", False, 300),
                        field("Phone number (optional)", "phone", "tel", False, 32),
                        rx.el.p(
                            "You choose separately whether to share your phone number with each connection.",
                            class_name="muted text-sm",
                        ),
                    ]
                    if registering or editing
                    else []
                ),
                *(
                    []
                    if editing
                    else [
                        field("Email", "email", "email", maximum=254),
                        field(
                            "Password (at least 10 characters)", "password", "password"
                        ),
                    ]
                ),
                button(
                    "Save profile"
                    if editing
                    else ("Create account" if registering else "Sign in"),
                    type="submit",
                    disabled=True,
                ),
                id="account-form",
                method="post",
                class_name="form-stack",
                custom_attrs=attrs(mode=mode),
            ),
            *(
                [
                    button("Sign out", variant="secondary", id="logout-button"),
                    link(
                        "Back to Intersect",
                        href="/",
                        class_name="btn primary profile-back",
                    ),
                ]
                if editing
                else [
                    link(
                        "Already registered? Sign in"
                        if registering
                        else "New here? Create an account",
                        href="/login" if registering else "/register",
                        class_name="text-link",
                    )
                ]
            ),
            rx.el.p(
                id="account-status",
                role="status",
                class_name="form-feedback",
                hidden=True,
                custom_attrs={"aria-live": "polite", "aria-atomic": "true"},
            ),
            *(
                [puzzle_widget(mode="accounts")]
                if mode == "login" else []
            ),
            class_name="account-card",
        ),
        api_config(),
        rx.script(src="/accounts.js"),
        class_name="account-page",
        custom_attrs=attrs(page=mode),
    )


def login():
    return account_page("login")


def register():
    return account_page("register")


def profile():
    return account_page("profile")
