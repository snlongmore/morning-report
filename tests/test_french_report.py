"""Tests for French report generation."""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from morning_report.report.generator import (
    generate_report,
    french_date,
    FRENCH_DAYS,
    FRENCH_MONTHS,
)
from morning_report.report.emailer import (
    _build_summary_fr,
    _build_subject_fr,
    build_message,
)
from morning_report.gatherers.news import _parse_feeds


# -- Shared test data --------------------------------------------------------

SAMPLE_DATA = {
    "weather": {
        "status": "ok",
        "locations": {
            "West Kirby, UK": {
                "current": {
                    "description": "overcast clouds",
                    "temp": 10.2,
                    "feels_like": 8.5,
                    "humidity": 82,
                    "wind_speed": 5.1,
                },
            }
        },
    },
    "calendar": {
        "status": "ok",
        "today": [
            {
                "title": "Research Group Meeting",
                "start": "2026-02-26T10:00:00",
                "end": "2026-02-26T11:00:00",
                "calendar": "Research Group",
                "location": "Byrom Street",
                "all_day": False,
            },
        ],
        "upcoming": [],
        "events": [
            {"start": "2026-02-26T10:00:00", "title": "Research Group Meeting"},
        ],
        "date_range": {"from": "2026-02-26", "to": "2026-02-28"},
    },
    "email": {
        "status": "ok",
        "total_unread": 14,
        "account_summary": {
            "LJMU": 5,
            "snlongmore@gmail.com": 9,
        },
        "accounts": {
            "LJMU": [{"sender": "a@b.com", "subject": "hi"}] * 5,
            "snlongmore@gmail.com": [{"sender": "c@d.com", "subject": "hello"}] * 9,
        },
        "needs_response": [],
    },
    "markets": {
        "status": "ok",
        "crypto": {
            "bitcoin": {"symbol": "BTC", "price_usd": 67943.50, "change_24h_pct": 2.3},
            "ethereum": {"symbol": "ETH", "price_usd": 2045.20, "change_24h_pct": -1.1},
        },
        "stocks": {},
    },
    "arxiv": {
        "status": "ok",
        "total_new": 26,
        "categories_searched": ["astro-ph.GA", "astro-ph.SR"],
        "tiers": {"1": [], "2": [], "3": []},
        "papers": [{"title": f"Paper {i}", "tier": 3} for i in range(26)],
    },
    "news": {
        "status": "ok",
        "categories": {
            "Astronomy": [
                {"title": "New Star Found", "link": "http://example.com", "source": "NASA"},
            ],
        },
        "total_articles": 1,
    },
    "news_fr": {
        "status": "ok",
        "categories": {
            "IA et technologie": [
                {
                    "title": "L'IA revolutionne la recherche",
                    "link": "http://lemonde.fr/article",
                    "source": "Le Monde",
                    "summary": "Un article sur l'intelligence artificielle.",
                },
            ],
            "Football": [
                {
                    "title": "PSG bat Marseille 3-1",
                    "link": "http://lequipe.fr/article",
                    "source": "L'Equipe",
                },
            ],
        },
        "total_articles": 2,
    },
    "meditation": {
        "status": "ok",
        "items": [
            {
                "title": "The Power of Letting Go",
                "summary": "Today's meditation focuses on surrender.",
                "content": "<p>Richard Rohr reflects on the practice of letting go...</p>",
                "link": "http://cac.org/meditation",
                "published": "2026-02-26",
                "source": "Center for Action and Contemplation",
            },
        ],
    },
}


# -- French date helpers -----------------------------------------------------

class TestFrenchDateHelpers:
    def test_french_days_complete(self):
        expected = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        assert set(FRENCH_DAYS.keys()) == expected

    def test_french_months_complete(self):
        assert set(FRENCH_MONTHS.keys()) == set(range(1, 13))

    def test_french_date_formatting(self):
        dt = datetime(2026, 2, 26)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 26 fevrier 2026"

    def test_french_date_january(self):
        dt = datetime(2026, 1, 1)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 1 janvier 2026"

    def test_french_date_december(self):
        dt = datetime(2025, 12, 25)  # Thursday
        result = french_date(dt)
        assert result == "jeudi 25 decembre 2025"


# -- French report generation -----------------------------------------------

class TestFrenchReportGeneration:
    def test_generates_french_report(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Rapport du matin" in report

    def test_french_report_filename(self, tmp_path):
        dt = datetime(2026, 2, 26)
        generate_report(SAMPLE_DATA, output_dir=tmp_path, date=dt, language="fr")
        assert (tmp_path / "2026-02-26-fr.md").exists()

    def test_english_report_filename_unchanged(self, tmp_path):
        dt = datetime(2026, 2, 26)
        generate_report(SAMPLE_DATA, output_dir=tmp_path, date=dt, language="en")
        assert (tmp_path / "2026-02-26.md").exists()
        assert not (tmp_path / "2026-02-26-fr.md").exists()

    def test_french_report_has_french_headers(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Emploi du temps" in report
        assert "Resume des courriels" in report
        assert "Marches" in report
        assert "Meteo" in report

    def test_french_report_has_french_date(self, tmp_path):
        dt = datetime(2026, 2, 26)
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, date=dt, language="fr")
        assert "jeudi 26 fevrier 2026" in report

    def test_french_report_calendar_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Heure" in report
        assert "Evenement" in report
        assert "Calendrier" in report

    def test_french_report_no_events(self, tmp_path):
        data = {
            "calendar": {
                "status": "ok",
                "today": [],
                "upcoming": [],
                "date_range": {"from": "2026-02-26", "to": "2026-02-28"},
            },
        }
        report = generate_report(data, output_dir=tmp_path, language="fr")
        assert "Aucun evenement" in report

    def test_french_report_markets_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Variation 24h" in report
        assert "Jeton" in report

    def test_french_report_weather_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "humidite" in report
        assert "vent" in report

    def test_french_report_arxiv_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Veille arXiv" in report
        assert "nouveaux articles" in report

    def test_french_report_news_fr_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Revue de presse francaise" in report
        assert "L'IA revolutionne la recherche" in report

    def test_french_report_meditation_section(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Meditation du jour" in report
        assert "The Power of Letting Go" in report

    def test_french_report_placeholder_sections(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Poeme du jour" in report
        assert "Ce jour dans l'histoire" in report
        assert "Lecon du jour" in report

    def test_french_report_ends_with_french(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="fr")
        assert "Fin du rapport du matin" in report

    def test_english_report_unchanged(self, tmp_path):
        report = generate_report(SAMPLE_DATA, output_dir=tmp_path, language="en")
        assert "Morning Report" in report
        assert "Today's Schedule" in report
        assert "Email Summary" in report
        assert "End of morning report" in report


# -- News gatherer summary/content extraction --------------------------------

class TestNewsSummaryExtraction:
    def test_summary_field_extracted(self):
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "Test Feed"
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "Test Article",
            "link": "http://example.com",
            "published": "2026-02-26",
            "summary": "This is the article summary.",
            "content": [{"value": "<p>Full content here.</p>"}],
        }.get(key, default)
        mock_feed.entries = [mock_entry]

        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.news.feedparser", mock_feedparser, create=True):
                result = _parse_feeds({"Test": ["http://example.com/rss"]})

        article = result["Test"][0]
        assert article["summary"] == "This is the article summary."
        assert article["content"] == "<p>Full content here.</p>"

    def test_missing_summary_not_included(self):
        mock_feed = MagicMock()
        mock_feed.feed.get.return_value = "Test Feed"
        mock_entry = MagicMock()
        mock_entry.get.side_effect = lambda key, default="": {
            "title": "No Summary Article",
            "link": "http://example.com",
            "published": "2026-02-26",
        }.get(key, default)
        mock_feed.entries = [mock_entry]

        mock_feedparser = MagicMock()
        mock_feedparser.parse.return_value = mock_feed

        with patch.dict("sys.modules", {"feedparser": mock_feedparser}):
            with patch("morning_report.gatherers.news.feedparser", mock_feedparser, create=True):
                result = _parse_feeds({"Test": ["http://example.com/rss"]})

        article = result["Test"][0]
        assert "summary" not in article
        assert "content" not in article


# -- French email summary ---------------------------------------------------

class TestFrenchEmailSummary:
    def test_build_summary_fr_includes_meteo(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "Meteo" in summary
        assert "West Kirby" in summary

    def test_build_summary_fr_includes_agenda(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "Agenda" in summary
        assert "evenements" in summary

    def test_build_summary_fr_includes_courriels(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "Courriels" in summary
        assert "non lus" in summary

    def test_build_summary_fr_includes_arxiv(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "arXiv" in summary
        assert "nouveaux articles" in summary

    def test_build_summary_fr_includes_marches(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "Marches" in summary
        assert "BTC" in summary

    def test_build_summary_fr_includes_pieces_jointes(self):
        summary = _build_summary_fr(SAMPLE_DATA)
        assert "pieces jointes" in summary

    def test_build_summary_fr_empty_data(self):
        summary = _build_summary_fr({})
        assert "Rapport du matin" in summary
        assert "pieces jointes" in summary

    def test_build_subject_fr(self):
        subject = _build_subject_fr()
        assert "Rapport du matin" in subject


# -- Dual attachment email ---------------------------------------------------

class TestDualAttachmentEmail:
    def test_build_message_with_french_docx(self, tmp_path):
        docx_path = tmp_path / "2026-02-26.docx"
        docx_path.write_bytes(b"fake english docx")
        docx_fr_path = tmp_path / "2026-02-26-fr.docx"
        docx_fr_path.write_bytes(b"fake french docx")
        json_path = tmp_path / "2026-02-26.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(
            docx_path=docx_path,
            json_path=json_path,
            recipient="test@example.com",
            sender="sender@example.com",
            docx_fr_path=docx_fr_path,
        )

        # Should have 3 parts: text body + 2 attachments
        parts = list(msg.iter_parts())
        assert len(parts) == 3
        filenames = [p.get_filename() for p in parts if p.get_filename()]
        assert "2026-02-26.docx" in filenames
        assert "2026-02-26-fr.docx" in filenames

    def test_build_message_french_subject(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        docx_fr_path = tmp_path / "report-fr.docx"
        docx_fr_path.write_bytes(b"fake french docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(
            docx_path=docx_path,
            json_path=json_path,
            recipient="test@example.com",
            sender="sender@example.com",
            docx_fr_path=docx_fr_path,
        )

        assert "Rapport du matin" in msg["Subject"]

    def test_build_message_french_body(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        docx_fr_path = tmp_path / "report-fr.docx"
        docx_fr_path.write_bytes(b"fake french docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(
            docx_path=docx_path,
            json_path=json_path,
            recipient="test@example.com",
            sender="sender@example.com",
            docx_fr_path=docx_fr_path,
        )

        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert "pieces jointes" in body

    def test_build_message_without_french_is_english(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(
            docx_path=docx_path,
            json_path=json_path,
            recipient="test@example.com",
            sender="sender@example.com",
        )

        assert "Morning Report" in msg["Subject"]
        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert "Full report attached" in body

        parts = list(msg.iter_parts())
        assert len(parts) == 2  # text + 1 attachment
