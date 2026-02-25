"""Tests for the email delivery module."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from morning_report.report.emailer import send_report, build_message, _build_summary


SAMPLE_DATA = {
    "weather": {
        "status": "ok",
        "locations": {
            "West Kirby, UK": {
                "current": {"description": "light rain", "temp": 11.5, "humidity": 85},
            }
        },
    },
    "calendar": {
        "status": "ok",
        "events": [],
    },
    "email": {
        "status": "ok",
        "accounts": [
            {"name": "gmail", "unread_count": 12},
            {"name": "work", "unread_count": 5},
        ],
    },
    "arxiv": {
        "status": "ok",
        "papers": [
            {"title": "Paper A", "tier": 1},
            {"title": "Paper B", "tier": 2},
            {"title": "Paper C", "tier": 3},
        ],
    },
    "markets": {
        "status": "ok",
        "crypto": {
            "bitcoin": {"symbol": "BTC", "price_usd": 65432.10},
            "allora": {"symbol": "ALLO", "price_usd": 0.0123},
        },
    },
}


class TestBuildSummary:
    def test_includes_weather(self):
        summary = _build_summary(SAMPLE_DATA)
        assert "West Kirby" in summary
        assert "light rain" in summary

    def test_includes_email_count(self):
        summary = _build_summary(SAMPLE_DATA)
        assert "17 unread" in summary
        assert "2 accounts" in summary

    def test_includes_arxiv(self):
        summary = _build_summary(SAMPLE_DATA)
        assert "3 new papers" in summary
        assert "1 tier 1" in summary

    def test_includes_markets(self):
        summary = _build_summary(SAMPLE_DATA)
        assert "BTC" in summary
        assert "ALLO" in summary

    def test_includes_full_report_attached(self):
        summary = _build_summary(SAMPLE_DATA)
        assert "Full report attached" in summary

    def test_handles_empty_data(self):
        summary = _build_summary({})
        assert "Morning Report" in summary
        assert "Full report attached" in summary


class TestBuildMessage:
    def test_message_structure(self, tmp_path):
        docx_path = tmp_path / "2026-02-25.docx"
        docx_path.write_bytes(b"fake docx content")
        json_path = tmp_path / "2026-02-25.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(
            docx_path=docx_path,
            json_path=json_path,
            recipient="test@example.com",
            sender="sender@example.com",
        )

        assert msg["Subject"].startswith("Morning Report")
        assert msg["From"] == "sender@example.com"
        assert msg["To"] == "test@example.com"

    def test_has_attachment(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(docx_path, json_path, "to@test.com", "from@test.com")

        # EmailMessage with attachment has multiple parts
        parts = list(msg.iter_parts())
        assert len(parts) == 2  # text body + attachment
        attachment = parts[1]
        assert attachment.get_filename() == "report.docx"

    def test_body_contains_summary(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        msg = build_message(docx_path, json_path, "to@test.com", "from@test.com")

        body = msg.get_body(preferencelist=("plain",)).get_content()
        assert "Full report attached" in body


class TestSendReport:
    def test_smtp_calls(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        mock_smtp = MagicMock()
        mock_smtp_instance = MagicMock()
        mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_smtp_instance)
        mock_smtp.return_value.__exit__ = MagicMock(return_value=False)

        with patch("morning_report.report.emailer.smtplib.SMTP", mock_smtp):
            send_report(
                docx_path=docx_path,
                json_path=json_path,
                recipient="test@example.com",
                sender="sender@example.com",
                app_password="test-password-123",
            )

        mock_smtp.assert_called_once_with("smtp.gmail.com", 587)
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with("sender@example.com", "test-password-123")
        mock_smtp_instance.send_message.assert_called_once()

    def test_raises_on_empty_password(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        with pytest.raises(ValueError, match="Gmail app password not configured"):
            send_report(docx_path, json_path, "to@test.com", "from@test.com", "")

    def test_raises_on_placeholder_password(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))

        with pytest.raises(ValueError, match="Gmail app password not configured"):
            send_report(docx_path, json_path, "to@test.com", "from@test.com", "${GMAIL_APP_PASSWORD}")

    def test_raises_on_missing_docx(self, tmp_path):
        json_path = tmp_path / "report.json"
        json_path.write_text(json.dumps(SAMPLE_DATA))
        missing_docx = tmp_path / "missing.docx"

        with pytest.raises(FileNotFoundError, match="Word document not found"):
            send_report(missing_docx, json_path, "to@test.com", "from@test.com", "password")

    def test_raises_on_missing_json(self, tmp_path):
        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(b"fake docx")
        missing_json = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError, match="JSON data not found"):
            send_report(docx_path, missing_json, "to@test.com", "from@test.com", "password")
