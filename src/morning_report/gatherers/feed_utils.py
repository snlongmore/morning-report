"""RSS feed parsing utilities."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def strip_html(text: str) -> str:
    """Remove HTML tags and collapse whitespace."""
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Markers that signal the end of actual article content (CAC meditation cruft)
_CONTENT_END_MARKERS = (
    "Reference:",
    "Image Credit:",
    "Image credit:",
    "Explore Further",
    "The post ",
    "Story from Our Community",
    "New at CAC",
)


def trim_article_content(text: str) -> str:
    """Trim website cruft that follows the actual article content.

    Looks for known markers (image credits, footer navigation, WordPress
    boilerplate) and truncates at the earliest one found.
    """
    if not text:
        return text

    earliest = len(text)
    for marker in _CONTENT_END_MARKERS:
        idx = text.find(marker)
        if idx != -1 and idx < earliest:
            earliest = idx

    return text[:earliest].strip()


def parse_feeds(feeds: dict[str, list[str]], max_per_category: int = 5) -> dict[str, list[dict]]:
    """Fetch and parse RSS feeds, grouped by category.

    Args:
        feeds: Mapping of category name to list of feed URLs.
        max_per_category: Maximum number of items per category.

    Returns:
        Dict mapping category to list of article dicts. If feedparser is
        missing, returns ``{"_error": "..."}`` instead.
    """
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
                    item: dict[str, Any] = {
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                        "source": feed.feed.get("title", url),
                    }
                    summary = entry.get("summary", "")
                    if summary:
                        item["summary"] = trim_article_content(strip_html(summary))
                    content_list = entry.get("content", [])
                    if content_list and isinstance(content_list, list):
                        raw_content = content_list[0].get("value", "")
                        if raw_content:
                            item["content"] = trim_article_content(strip_html(raw_content))
                    items.append(item)
            except Exception as e:
                logger.warning("Failed to parse feed %s: %s", url, e)

        results[category] = items[:max_per_category]

    return results
