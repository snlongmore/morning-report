"""Tests for configuration loader."""

import os
from pathlib import Path

import pytest

from morning_report.config import _expand_env_vars, load_config


def test_expand_env_vars_string(monkeypatch):
    monkeypatch.setenv("TEST_TOKEN", "abc123")
    assert _expand_env_vars("${TEST_TOKEN}") == "abc123"


def test_expand_env_vars_missing():
    """Unexpanded vars are left as-is."""
    result = _expand_env_vars("${DEFINITELY_NOT_SET_12345}")
    assert result == "${DEFINITELY_NOT_SET_12345}"


def test_expand_env_vars_nested(monkeypatch):
    monkeypatch.setenv("MY_KEY", "secret")
    data = {"a": {"b": "${MY_KEY}"}, "c": ["${MY_KEY}", "literal"]}
    expanded = _expand_env_vars(data)
    assert expanded["a"]["b"] == "secret"
    assert expanded["c"] == ["secret", "literal"]


def test_load_config_example():
    """Loading with no config.yaml should fall back to example."""
    # This test works because config.example.yaml exists
    cfg = load_config()
    assert "user" in cfg
    assert cfg["user"]["name"] == "Steven Longmore"


def test_load_config_missing(tmp_path):
    """Loading from a nonexistent path should raise."""
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "nonexistent.yaml")
