"""News gatherer via RSS feeds."""

from __future__ import annotations

import logging
import re
from typing import Any

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

# Default RSS feeds when none are configured
_DEFAULT_FEEDS = {
    "Astronomy": [
        "https://www.eso.org/public/news/feed/",
        "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    ],
    "AI/ML": [
        "https://news.ycombinator.com/rss",
    ],
    "Shipping": [
        "https://gcaptain.com/feed/",
        "https://splash247.com/feed/",
    ],
    "Crypto": [
        "https://cointelegraph.com/rss",
    ],
}


def _parse_feeds(feeds: dict[str, list[str]], max_per_category: int = 5) -> dict[str, list[dict]]:
    """Fetch and parse RSS feeds, grouped by category."""
    try:
        import feedparser
    except ImportError:
        return {"_error": "feedparser not installed. Run: uv pip install feedparser"}

    results: dict[str, list[dict]] = {}

    for category, urls in feeds.items():
        items: list[dict] = []
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:max_per_category]:
                    item = {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                    }
                    # Extract summary and full content when available (HTML stripped)
                    summary = entry.get("summary", "")
                    if summary:
                        item["summary"] = _strip_html(summary)
                    content_list = entry.get("content", [])
                    if content_list and isinstance(content_list, list):
                        raw_content = content_list[0].get("value", "")
                        if raw_content:
                            item["content"] = _strip_html(raw_content)
                    items.append(item)
            except Exception as e:
                logger.warning("Failed to parse feed %s: %s", url, e)

        # Sort by published date (newest first) and limit
        results[category] = items[:max_per_category]

    return results


class NewsGatherer(BaseGatherer):
    """Gathers news from RSS feeds."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._feeds = self._config.get("feeds", {})
        self._max_per_category = self._config.get("max_per_category", 5)

    @property
    def name(self) -> str:
        return "news"

    def gather(self) -> dict[str, Any]:
        """Fetch news from configured RSS feeds."""
        feeds = self._feeds if self._feeds else _DEFAULT_FEEDS
        articles = _parse_feeds(feeds, self._max_per_category)

        if "_error" in articles:
            raise RuntimeError(articles["_error"])

        total = sum(len(items) for items in articles.values())
        return {
            "categories": articles,
            "total_articles": total,
        }
