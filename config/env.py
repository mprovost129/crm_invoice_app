"""Small, testable helpers for environment-driven Django configuration."""

import os

from django.core.exceptions import ImproperlyConfigured


def required_env(name: str) -> str:
    """Return a non-empty environment value or fail with an actionable message."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(f"Required environment variable {name} is not set.")
    return value


def csv_env(name: str, *, required: bool = False) -> list[str]:
    """Parse a comma-separated environment setting, dropping empty values."""
    values = [value.strip() for value in os.environ.get(name, "").split(",")]
    parsed = [value for value in values if value]
    if required and not parsed:
        raise ImproperlyConfigured(
            f"Required comma-separated environment variable {name} is not set."
        )
    return parsed


def bool_env(name: str, *, default: bool = False) -> bool:
    """Parse a conventional boolean environment value."""
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"Environment variable {name} must be a boolean value.")


def validate_production_secret(secret_key: str) -> str:
    """Reject placeholder or weak Django secret keys in production."""
    if secret_key in {"replace-me", "build-only-key"} or len(secret_key) < 50:
        raise ImproperlyConfigured(
            "Production SECRET_KEY must be unique, non-placeholder, and at least "
            "50 characters."
        )
    return secret_key
