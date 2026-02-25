"""Tests for the GitHub gatherer."""

import json
from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.github import GitHubGatherer, _gh_json


class TestGhJson:
    def test_successful_call(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '[{"title": "Fix bug"}]'
        mock_result.stderr = ""

        with patch("morning_report.gatherers.github.subprocess.run", return_value=mock_result):
            result = _gh_json(["api", "notifications"])

        assert result == [{"title": "Fix bug"}]

    def test_empty_output(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""

        with patch("morning_report.gatherers.github.subprocess.run", return_value=mock_result):
            result = _gh_json(["api", "notifications"])

        assert result == []

    def test_gh_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "not authenticated"

        with patch("morning_report.gatherers.github.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="not authenticated"):
                _gh_json(["api", "notifications"])


class TestGitHubGatherer:
    def test_name(self):
        g = GitHubGatherer()
        assert g.name == "github"

    def test_available_when_gh_installed(self):
        with patch("morning_report.gatherers.github.shutil.which", return_value="/usr/local/bin/gh"):
            g = GitHubGatherer()
            assert g.is_available()

    def test_not_available_when_gh_missing(self):
        with patch("morning_report.gatherers.github.shutil.which", return_value=None):
            g = GitHubGatherer()
            assert not g.is_available()

    def test_gather_returns_all_sections(self):
        notifs = [
            {"title": "PR review requested", "type": "PullRequest", "repo": "org/repo", "reason": "review_requested", "updated_at": "2026-02-25T10:00:00Z"},
        ]
        prs = [
            {"title": "Add feature X", "url": "https://github.com/org/repo/pull/1", "repository": {"nameWithOwner": "org/repo"}},
        ]
        issues = [
            {"title": "Bug in Y", "url": "https://github.com/org/repo/issues/2", "repository": {"nameWithOwner": "org/repo"}},
        ]

        call_count = 0

        def mock_gh_json(args, timeout=15):
            nonlocal call_count
            call_count += 1
            if "notifications" in args:
                return notifs
            elif "prs" in args:
                return prs
            elif "issues" in args:
                return issues
            return []

        with patch("morning_report.gatherers.github._gh_json", side_effect=mock_gh_json):
            g = GitHubGatherer()
            result = g.gather()

        assert result["notification_count"] == 1
        assert len(result["prs_to_review"]) == 1
        assert result["prs_to_review"][0]["title"] == "Add feature X"
        assert len(result["assigned_issues"]) == 1

    def test_gather_handles_failures_gracefully(self):
        with patch("morning_report.gatherers.github._gh_json", side_effect=RuntimeError("gh auth failed")):
            g = GitHubGatherer()
            result = g.gather()

        assert result["notification_count"] == 0
        assert result["prs_to_review"] == []
        assert result["assigned_issues"] == []

    def test_safe_gather_ok(self):
        with patch("morning_report.gatherers.github._gh_json", return_value=[]):
            g = GitHubGatherer()
            result = g.safe_gather()

        assert result["status"] == "ok"
