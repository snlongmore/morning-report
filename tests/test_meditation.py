"""Tests for the MeditationGatherer."""

from unittest.mock import patch, MagicMock

from morning_report.gatherers.meditation import MeditationGatherer, _DEFAULT_FEED_URL


class TestMeditationGatherer:
    def test_name(self):
        g = MeditationGatherer()
        assert g.name == "meditation"

    def test_default_feed_url(self):
        g = MeditationGatherer()
        assert g._feed_url == _DEFAULT_FEED_URL

    def test_custom_feed_url(self):
        g = MeditationGatherer(config={"feed_url": "http://custom.com/feed"})
        assert g._feed_url == "http://custom.com/feed"

    def test_gather_success(self):
        mock_items = [
            {
                "title": "The Power of Letting Go",
                "link": "http://cac.org/meditation",
                "published": "2026-03-01",
                "summary": "Today's meditation.",
                "content": "Full meditation text here.",
                "source": "Center for Action and Contemplation",
            }
        ]

        with patch("morning_report.gatherers.meditation.parse_feeds") as mock_parse:
            mock_parse.return_value = {"meditation": mock_items}
            result = MeditationGatherer().gather()

        assert result["items"] == mock_items
        mock_parse.assert_called_once_with(
            {"meditation": [_DEFAULT_FEED_URL]}, max_per_category=1
        )

    def test_gather_empty(self):
        with patch("morning_report.gatherers.meditation.parse_feeds") as mock_parse:
            mock_parse.return_value = {"meditation": []}
            result = MeditationGatherer().gather()

        assert result["items"] == []

    def test_gather_feedparser_missing(self):
        with patch("morning_report.gatherers.meditation.parse_feeds") as mock_parse:
            mock_parse.return_value = {"_error": "feedparser not installed"}
            try:
                MeditationGatherer().gather()
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "feedparser" in str(e)

    def test_safe_gather_wraps_errors(self):
        with patch("morning_report.gatherers.meditation.parse_feeds") as mock_parse:
            mock_parse.side_effect = Exception("Network timeout")
            result = MeditationGatherer().safe_gather()

        assert result["status"] == "error"
        assert "Network timeout" in result["error"]

    def test_is_available_always_true(self):
        g = MeditationGatherer()
        assert g.is_available() is True
