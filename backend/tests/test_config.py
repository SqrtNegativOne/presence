"""Tests for env-driven backend configuration."""

import pytest
from fastapi import HTTPException

import config


def test_require_cloud_mode_noop_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "CLOUD_MODE_ENABLED", True)
    assert config.require_cloud_mode() is None


def test_require_cloud_mode_raises_503_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "CLOUD_MODE_ENABLED", False)
    with pytest.raises(HTTPException) as exc_info:
        config.require_cloud_mode()
    assert exc_info.value.status_code == 503
    assert "Cloud mode is disabled" in exc_info.value.detail


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_bool_helper(monkeypatch, raw, expected):
    monkeypatch.setenv("PRESENCE_TEST_BOOL", raw)
    assert config._bool("PRESENCE_TEST_BOOL", not expected) is expected


def test_bool_helper_uses_default(monkeypatch):
    monkeypatch.delenv("PRESENCE_TEST_BOOL", raising=False)
    assert config._bool("PRESENCE_TEST_BOOL", True) is True
    assert config._bool("PRESENCE_TEST_BOOL", False) is False
