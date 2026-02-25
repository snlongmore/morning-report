"""Configuration loader with environment variable expansion."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")

# Default config path relative to project root
_DEFAULT_CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "config.yaml"


def _expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR} references in strings."""
    if isinstance(value, str):
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return _ENV_VAR_PATTERN.sub(_replace, value)
    if isinstance(value, dict):
        return {k: _expand_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env_vars(item) for item in value]
    return value


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load YAML config, expanding environment variable references.

    Args:
        path: Path to config file. Defaults to config/config.yaml in the project root.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If the config file does not exist.
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG

    if not config_path.exists():
        # Fall back to example config if main config missing
        example = config_path.with_suffix(".example.yaml")
        if example.name == "config.example.yaml":
            example = config_path.parent / "config.example.yaml"
        if example.exists():
            config_path = example
        else:
            raise FileNotFoundError(
                f"Config file not found: {config_path}\n"
                f"Copy config/config.example.yaml to config/config.yaml and fill in your values."
            )

    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return _expand_env_vars(raw or {})


def get_project_root() -> Path:
    """Return the project root directory (where pyproject.toml lives)."""
    return Path(__file__).resolve().parent.parent.parent
