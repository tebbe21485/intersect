"""Shared input validation and the initial content moderation policy."""

import re
from urllib.parse import urlparse

from better_profanity import profanity

from .errors import AppError


def text(value, label="Text", maximum=1000, required=True, filtered=True):
    if not isinstance(value, str):
        raise AppError(f"{label} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > maximum:
        raise AppError(
            f"{label} must contain {'1' if required else '0'}–{maximum} characters."
        )
    if filtered and profanity.contains_profanity(value):
        raise AppError(f"Please edit {label.lower()} to remove inappropriate language.")
    return value


def identifier(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        raise AppError("Invalid record ID.")
    try:
        number = int(value)
    except (ValueError, TypeError):
        raise AppError("Invalid record ID.") from None
    if number < 1:
        raise AppError("Invalid record ID.")
    return number


def email(value):
    value = text(value, "Email", 254, filtered=False).casefold()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise AppError("Enter a valid email address.")
    return value


def password(value):
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise AppError("Use a password of 10–128 characters.")
    return value


def profile_fields(payload):
    first = text(payload.get("firstName"), "First name", 80)
    last = text(payload.get("lastName"), "Last name", 80)
    linkedin = text(payload.get("linkedin", ""), "LinkedIn", 300, False, False)
    if linkedin:
        parsed = urlparse(linkedin)
        if (
            parsed.scheme != "https"
            or parsed.hostname not in ("linkedin.com", "www.linkedin.com")
            or parsed.username
            or parsed.password
        ):
            raise AppError("Use an https://www.linkedin.com/ profile URL.")
    phone = text(payload.get("phone", ""), "Phone number", 32, False, False)
    if phone and not re.fullmatch(r"[+\d ()\-.]{7,32}", phone):
        raise AppError(
            "Enter a phone number using digits, spaces and an optional country code."
        )
    return first, last, linkedin, phone


def boolean(value, label):
    if not isinstance(value, bool):
        raise AppError(f"{label} must be true or false.")
    return value
