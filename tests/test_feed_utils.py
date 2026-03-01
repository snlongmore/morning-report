"""Tests for RSS feed parsing utilities."""

from unittest.mock import patch, MagicMock

from morning_report.gatherers.feed_utils import strip_html, parse_feeds


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_no_tags(self):
        assert strip_html("No tags here") == "No tags here"

    def test_nested_tags(self):
        assert strip_html("<div><p>Nested</p></div>") == "Nested"

    def test_collapses_whitespace(self):
        assert strip_html("<p>Line one</p>\n\n<p>Line two</p>") == "Line one Line two"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_self_closing_tags(self):
        assert strip_html("Hello<br/>World") == "HelloWorld"


class TestParseFeeds:
    def _make_mock_feed(self, entries, feed_title="Test Feed"):
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = feed_title
        mock_feed.entries = entries
        return mock_feed

    def _make_mock_entry(self, data):
        entry = MagicMock()
        entry.get.side_effect = lambda key, default="": data.get(key, default)
        return entry

    def test_basic_parsing(self):
        entry = self._make_mock_entry({
            "title": "Test Article",
            "link": "http://example.com",
            "published": "2026-03-01",
            "summary": "A summary.",
        })
        mock_feed = self._make_mock_feed([entry])
        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({"News": ["http://example.com/rss"]})

        assert "News" in result
        assert len(result["News"]) == 1
        assert result["News"][0]["title"] == "Test Article"
        assert result["News"][0]["summary"] == "A summary."

    def test_content_extraction(self):
        entry = self._make_mock_entry({
            "title": "Article",
            "link": "http://example.com",
            "published": "2026-03-01",
            "summary": "Brief",
            "content": [{"value": "<p>Full <b>content</b> here.</p>"}],
        })
        mock_feed = self._make_mock_feed([entry])
        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({"Test": ["http://example.com/rss"]})

        assert result["Test"][0]["content"] == "Full content here."

    def test_missing_summary_excluded(self):
        entry = self._make_mock_entry({
            "title": "No Summary",
            "link": "http://example.com",
            "published": "2026-03-01",
        })
        mock_feed = self._make_mock_feed([entry])
        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({"Test": ["http://example.com/rss"]})

        assert "summary" not in result["Test"][0]
        assert "content" not in result["Test"][0]

    def test_max_per_category(self):
        entries = [
            self._make_mock_entry({
                "title": f"Article {i}",
                "link": f"http://example.com/{i}",
                "published": "2026-03-01",
            })
            for i in range(10)
        ]
        mock_feed = self._make_mock_feed(entries)
        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({"Test": ["http://example.com/rss"]}, max_per_category=3)

        assert len(result["Test"]) == 3

    def test_multiple_categories(self):
        entry = self._make_mock_entry({
            "title": "Item",
            "link": "http://example.com",
            "published": "2026-03-01",
        })
        mock_feed = self._make_mock_feed([entry])
        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({
                    "Cat A": ["http://a.com/rss"],
                    "Cat B": ["http://b.com/rss"],
                })

        assert "Cat A" in result
        assert "Cat B" in result

    def test_feedparser_not_installed(self):
        with patch.dict("sys.modules", {"feedparser": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                # parse_feeds handles the ImportError internally
                result = parse_feeds({"Test": ["http://example.com/rss"]})
        assert "_error" in result

    def test_feed_parse_error_handled(self):
        mock_feedparser = MagicMock()
        mock_feedparser.parse.side_effect = Exception("Network error")

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.feed_utils.feedparser", mock_feedparser, create=True):
                result = parse_feeds({"Test": ["http://example.com/rss"]})

        assert result["Test"] == []
