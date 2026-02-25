"""Tests for the calendar gatherer."""

import json
import platform
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.calendar import CalendarGatherer


class TestCalendarGatherer:
    def test_name(self):
        g = CalendarGatherer()
        assert g.name == "calendar"

    @pytest.mark.skipif(platform.system() != "Darwin", reason="macOS only")
    def test_is_available(self):
        g = CalendarGatherer()
        assert g.is_available()

    def test_gather_parses_events(self):
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = (today.replace(day=today.day + 1)).strftime("%Y-%m-%d")

        fake_output = json.dumps([
            {
                "calendar": "LJMU",
                "title": "Research Group Meeting",
                "start": f"{today_str}T10:00:00",
                "end": f"{today_str}T11:00:00",
                "location": "Room 123",
                "notes": "",
                "all_day": False,
            },
            {
                "calendar": "family",
                "title": "Dinner",
                "start": f"{tomorrow_str}T19:00:00",
                "end": f"{tomorrow_str}T21:00:00",
                "location": "Home",
                "notes": "",
                "all_day": False,
            },
        ])

        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output, stderr="")
            g = CalendarGatherer(config={"calendars": ["LJMU", "family"], "lookahead_days": 3})
            result = g.gather()

        assert result["total_events"] == 2
        assert len(result["today"]) == 1
        assert result["today"][0]["title"] == "Research Group Meeting"
        assert len(result["upcoming"]) == 1

    def test_gather_empty_calendar(self):
        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
            g = CalendarGatherer()
            result = g.gather()

        assert result["total_events"] == 0
        assert result["today"] == []

    def test_gather_all_day_event(self):
        today_str = datetime.now().strftime("%Y-%m-%d")

        fake_output = json.dumps([
            {
                "calendar": "Steven Longmore",
                "title": "Conference",
                "start": f"{today_str}T00:00:00",
                "end": f"{today_str}T23:59:59",
                "location": "",
                "notes": "",
                "all_day": True,
            },
        ])

        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output, stderr="")
            g = CalendarGatherer()
            result = g.gather()

        assert result["today"][0]["all_day"] is True

    def test_gather_script_failure(self):
        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="Permission denied")
            g = CalendarGatherer()

            with pytest.raises(RuntimeError, match="Permission denied"):
                g.gather()

    def test_gather_access_denied_json(self):
        error_json = json.dumps({"error": "Calendar access denied."})
        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout=error_json, stderr="")
            g = CalendarGatherer()

            with pytest.raises(RuntimeError, match="Calendar access denied"):
                g.gather()

    def test_gather_deduplicates_events(self):
        today_str = datetime.now().strftime("%Y-%m-%d")

        fake_output = json.dumps([
            {
                "calendar": "ARI colloquia",
                "title": "ARI Seminar",
                "start": f"{today_str}T14:00:00",
                "end": f"{today_str}T15:00:00",
                "location": "Room 123",
                "notes": "",
                "all_day": False,
            },
            {
                "calendar": "ARI Seminars",
                "title": "ARI Seminar",
                "start": f"{today_str}T14:00:00",
                "end": f"{today_str}T15:00:00",
                "location": "",
                "notes": "",
                "all_day": False,
            },
        ])

        with patch("morning_report.gatherers.calendar.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=fake_output, stderr="")
            g = CalendarGatherer()
            result = g.gather()

        assert result["total_events"] == 1
        assert len(result["today"]) == 1
        assert result["today"][0]["calendar"] == "ARI colloquia"
