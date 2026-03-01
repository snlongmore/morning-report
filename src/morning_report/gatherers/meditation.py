"""Meditation gatherer — fetches the daily Richard Rohr meditation via RSS."""

from __future__ import annotations

import logging
from typing import Any

from morning_report.gatherers.base import BaseGatherer
from morning_report.gatherers.feed_utils import parse_feeds

logger = logging.getLogger(__name__)

_DEFAULT_FEED_URL = "https://cac.org/category/daily-meditations/feed/"


class MeditationGatherer(BaseGatherer):
    """Fetches the daily meditation from the CAC RSS feed."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._feed_url = self._config.get("feed_url", _DEFAULT_FEED_URL)

    @property
    def name(self) -> str:
        return "meditation"

    def gather(self) -> dict[str, Any]:
        """Fetch the latest meditation entry."""
        articles = parse_feeds({"meditation": [self._feed_url]}, max_per_category=1)

        if "_error" in articles:
            raise RuntimeError(articles["_error"])

        items = articles.get("meditation", [])
        return {"items": items}
