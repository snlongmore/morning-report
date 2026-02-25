"""macOS Calendar gatherer via Swift EventKit.

Uses a Swift helper script that calls EventKit directly — much faster than
AppleScript, which times out on calendars with many recurring events.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_SWIFT_SCRIPT = Path(__file__).parent.parent / "helpers" / "calendar_events.swift"


class CalendarGatherer(BaseGatherer):
    """Gathers calendar events from macOS Calendar via EventKit."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._calendars = self._config.get("calendars", ["Calendar"])
        self._lookahead = self._config.get("lookahead_days", 3)

    @property
    def name(self) -> str:
        return "calendar"

    def is_available(self) -> bool:
        import platform
        return platform.system() == "Darwin" and _SWIFT_SCRIPT.exists()

    def gather(self) -> dict[str, Any]:
        """Fetch upcoming events from configured calendars via EventKit."""
        cal_arg = ",".join(self._calendars)

        result = subprocess.run(
            ["swift", str(_SWIFT_SCRIPT), str(self._lookahead), cal_arg],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            stdout = result.stdout.strip()
            # Check for access denied in stdout (JSON error object)
            if stdout:
                try:
                    err_obj = json.loads(stdout)
                    if "error" in err_obj:
                        raise RuntimeError(err_obj["error"])
                except (json.JSONDecodeError, TypeError):
                    pass
            raise RuntimeError(f"Swift calendar script failed: {stderr or stdout}")

        raw = result.stdout.strip()
        if not raw or raw == "[]":
            return {"today": [], "upcoming": [], "total_events": 0}

        events = json.loads(raw)

        # Partition into today vs upcoming
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")
        today_events = []
        upcoming_events = []

        for evt in events:
            start_str = evt.get("start", "")
            # EventKit returns ISO format: YYYY-MM-DDTHH:MM:SS
            if start_str.startswith(today_str):
                today_events.append(evt)
            else:
                upcoming_events.append(evt)

        return {
            "today": today_events,
            "upcoming": upcoming_events,
            "total_events": len(events),
            "date_range": {
                "from": today_str,
                "to": (today + timedelta(days=self._lookahead)).strftime("%Y-%m-%d"),
            },
        }
