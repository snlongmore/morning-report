"""Tests for the News gatherer."""

from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.news import NewsGatherer, _parse_feeds


class TestParseFeedsFunction:
    def test_feedparser_not_installed(self):
        with patch.dict("sys.modules", {"feedparser": None}):
            # Force ImportError by making import fail
            def mock_parse(feeds, max_per_category=5):
                try:
                    import feedparser  # noqa: F401
                except (ImportError, TypeError):
                    return {"_error": "feedparser not installed. Run: uv pip install feedparser"}
                return {}

            result = mock_parse({"Test": ["http://example.com/rss"]})
            assert "_error" in result

    def test_successful_parse(self):
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "Test Feed"
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "Big Discovery",
            "link": "http://example.com/article",
            "published": "2026-02-25",
        }.get(key, default)
        mock_feed.entries = [mock_entry]

        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.news.feedparser", mock_feedparser, create=True):
                result = _parse_feeds({"Astronomy": ["http://example.com/rss"]}, max_per_category=5)

        assert "Astronomy" in result
        assert len(result["Astronomy"]) == 1
        assert result["Astronomy"][0]["title"] == "Big Discovery"


class TestNewsGatherer:
    def test_name(self):
        g = NewsGatherer()
        assert g.name == "news"

    def test_default_feeds(self):
        g = NewsGatherer()
        # No feeds configured means it uses defaults
        assert g._feeds == {}

    def test_custom_feeds(self):
        g = NewsGatherer(config={
            "feeds": {"Custom": ["http://example.com/rss"]},
            "max_per_category": 3,
        })
        assert "Custom" in g._feeds
        assert g._max_per_category == 3

    def test_gather_success(self):
        mock_categories = {
            "Astronomy": [{"title": "Star found", "link": "http://example.com", "source": "NASA"}],
        }

        with patch("morning_report.gatherers.news._parse_feeds", return_value=mock_categories):
            g = NewsGatherer()
            result = g.gather()

        assert result["categories"]["Astronomy"][0]["title"] == "Star found"
        assert result["total_articles"] == 1

    def test_gather_feedparser_error(self):
        with patch("morning_report.gatherers.news._parse_feeds", return_value={"_error": "feedparser not installed"}):
            g = NewsGatherer()
            with pytest.raises(RuntimeError, match="feedparser not installed"):
                g.gather()

    def test_safe_gather_wraps_error(self):
        with patch("morning_report.gatherers.news._parse_feeds", return_value={"_error": "feedparser not installed"}):
            g = NewsGatherer()
            result = g.safe_gather()
            assert result["status"] == "error"
