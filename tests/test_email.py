"""Tests for the email gatherer."""

import json
import platform
from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.email import EmailGatherer, _needs_response


class TestNeedsResponse:
    def test_question_mark(self):
        assert _needs_response("Meeting tomorrow?", "")

    def test_action_required(self):
        assert _needs_response("Action Required: Review PR", "")

    def test_please(self):
        assert _needs_response("Report", "Please review the attached document")

    def test_newsletter_no_response(self):
        assert not _needs_response("Weekly Newsletter", "Here are the top stories this week")


class TestEmailGatherer:
    def test_name(self):
        g = EmailGatherer()
        assert g.name == "email"

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_is_available(self):
        g = EmailGatherer()
        assert g.is_available()

    def test_gather_parses_applescript_output(self):
        """Test that gather correctly parses AppleScript JSON output."""
        fake_output = json.dumps([
            {
                "account": "LJMU",
                "sender": "colleague@ljmu.ac.uk",
                "subject": "Meeting tomorrow?",
                "date_received": "Tuesday, 25 February 2026 at 08:30:00",
                "snippet": "Hi Steve, can we meet tomorrow to discuss the paper?",
            },
            {
                "account": "snlongmore@gmail.com",
                "sender": "newsletter@arxiv.org",
                "subject": "arXiv daily digest",
                "date_received": "Tuesday, 25 February 2026 at 06:00:00",
                "snippet": "New papers in astro-ph today...",
            },
        ])

        with patch("morning_report.gatherers.email.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=fake_output,
                stderr="",
            )
            g = EmailGatherer()
            result = g.gather()

        assert result["total_unread"] == 2
        assert "LJMU" in result["account_summary"]
        assert result["account_summary"]["LJMU"] == 1
        assert len(result["needs_response"]) == 1  # The one with "?"

    def test_gather_empty_inbox(self):
        with patch("morning_report.gatherers.email.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            g = EmailGatherer()
            result = g.gather()

        assert result["total_unread"] == 0
        assert result["accounts"] == {}

    def test_vip_sender_flagged(self):
        fake_output = json.dumps([
            {
                "account": "test",
                "sender": "boss@example.com",
                "subject": "FYI",
                "date_received": "now",
                "snippet": "Just an update",
            },
        ])

        with patch("morning_report.gatherers.email.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output, stderr="")
            g = EmailGatherer(config={"vip_senders": ["boss@example.com"]})
            result = g.gather()

        assert len(result["needs_response"]) == 1
        assert result["needs_response"][0]["_is_vip"]
