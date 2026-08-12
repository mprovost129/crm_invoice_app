import pytest
from django.core.exceptions import ImproperlyConfigured

from config.env import bool_env, csv_env, required_env, validate_production_secret


def test_required_env_returns_trimmed_value(monkeypatch):
    monkeypatch.setenv("TEST_REQUIRED_SETTING", " value ")
    assert required_env("TEST_REQUIRED_SETTING") == "value"


def test_required_env_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("TEST_REQUIRED_SETTING", raising=False)
    with pytest.raises(ImproperlyConfigured, match="TEST_REQUIRED_SETTING"):
        required_env("TEST_REQUIRED_SETTING")


def test_csv_env_ignores_blank_items(monkeypatch):
    monkeypatch.setenv("TEST_CSV_SETTING", "one, two, ,three")
    assert csv_env("TEST_CSV_SETTING") == ["one", "two", "three"]


def test_required_csv_env_rejects_missing_value(monkeypatch):
    monkeypatch.delenv("TEST_CSV_SETTING", raising=False)
    with pytest.raises(ImproperlyConfigured, match="TEST_CSV_SETTING"):
        csv_env("TEST_CSV_SETTING", required=True)


@pytest.mark.parametrize("value", ["invalid", "2", "sometimes"])
def test_bool_env_rejects_ambiguous_values(monkeypatch, value):
    monkeypatch.setenv("TEST_BOOL_SETTING", value)
    with pytest.raises(ImproperlyConfigured, match="TEST_BOOL_SETTING"):
        bool_env("TEST_BOOL_SETTING")


@pytest.mark.parametrize("value", ["replace-me", "short", "build-only-key"])
def test_production_secret_rejects_placeholders_and_short_values(value):
    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        validate_production_secret(value)


def test_production_secret_accepts_long_unique_value():
    value = "a-unique-production-secret-key-that-is-longer-than-fifty-characters"
    assert validate_production_secret(value) == value
