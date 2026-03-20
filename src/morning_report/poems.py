"""Curated French poetry selection for the daily report.

Loads verified poem excerpts from a local JSON file and selects one
deterministically by date, so the same date always produces the same poem
and consecutive days produce different poems.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_POEMS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "poems.json"


def load_poems(path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load and validate poems from the JSON data file.

    Args:
        path: Path to the poems JSON file. Defaults to ``data/poems.json``
              relative to the project root.

    Returns:
        List of poem dicts, each with keys: title, author, source, excerpt, themes.

    Raises:
        FileNotFoundError: If the poems file does not exist.
        ValueError: If the JSON is invalid or a poem entry is malformed.
    """
    poems_path = Path(path) if path else _DEFAULT_POEMS_PATH

    with open(poems_path) as f:
        poems = json.load(f)

    if not isinstance(poems, list) or len(poems) == 0:
        raise ValueError(f"poems.json must be a non-empty list, got {type(poems).__name__}")

    required_keys = {"title", "author", "source", "excerpt"}
    for i, poem in enumerate(poems):
        missing = required_keys - set(poem.keys())
        if missing:
            raise ValueError(f"Poem at index {i} missing keys: {missing}")

    return poems


def select_poem(date: datetime, poems: list[dict[str, Any]]) -> dict[str, Any]:
    """Select a poem deterministically based on the date.

    Uses ``(day_of_year + year) % len(poems)`` so that:
    - The same date always returns the same poem (reproducible reports).
    - Consecutive days return different poems.

    Args:
        date: The report date.
        poems: List of poem dicts from :func:`load_poems`.

    Returns:
        A single poem dict.
    """
    index = (date.timetuple().tm_yday + date.year) % len(poems)
    return poems[index]
