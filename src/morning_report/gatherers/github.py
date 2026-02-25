"""GitHub gatherer via gh CLI."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)


def _gh_json(args: list[str], timeout: int = 15) -> Any:
    """Run a gh CLI command and parse JSON output."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh failed: {result.stderr.strip()}")
    if not result.stdout.strip():
        return []
    return json.loads(result.stdout)


class GitHubGatherer(BaseGatherer):
    """Gathers GitHub notifications, PRs, and issues via gh CLI."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}

    @property
    def name(self) -> str:
        return "github"

    def is_available(self) -> bool:
        return shutil.which("gh") is not None

    def gather(self) -> dict[str, Any]:
        """Fetch notifications, assigned PRs, and assigned issues."""
        result: dict[str, Any] = {}

        # Notifications
        try:
            notifs = _gh_json([
                "api", "notifications",
                "--jq", '[.[] | {title: .subject.title, type: .subject.type, repo: .repository.full_name, reason: .reason, updated_at: .updated_at}]',
            ])
            result["notifications"] = notifs[:20]  # Cap at 20
            result["notification_count"] = len(notifs)
        except Exception as e:
            logger.warning("Failed to fetch notifications: %s", e)
            result["notifications"] = []
            result["notification_count"] = 0

        # PRs requesting my review
        try:
            prs = _gh_json([
                "search", "prs",
                "--state=open",
                "--review-requested=@me",
                "--json", "title,url,repository,author,createdAt",
                "--limit", "10",
            ])
            result["prs_to_review"] = prs
        except Exception as e:
            logger.warning("Failed to fetch PRs: %s", e)
            result["prs_to_review"] = []

        # Issues assigned to me
        try:
            issues = _gh_json([
                "search", "issues",
                "--assignee=@me",
                "--state=open",
                "--json", "title,url,repository,labels,createdAt",
                "--limit", "10",
            ])
            result["assigned_issues"] = issues
        except Exception as e:
            logger.warning("Failed to fetch issues: %s", e)
            result["assigned_issues"] = []

        return result
