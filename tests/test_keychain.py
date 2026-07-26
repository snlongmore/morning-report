"""Tests for macOS Keychain secret storage."""

from unittest.mock import MagicMock, patch

import pytest

from morning_report import keychain


class TestGetSecret:
    def test_returns_stripped_value(self):
        result = MagicMock(returncode=0, stdout="s3cret\n")
        with patch("morning_report.keychain.subprocess.run", return_value=result) as mock_run:
            assert keychain.get_secret("svc", "acct") == "s3cret"

        assert mock_run.call_args[0][0] == [
            "security", "find-generic-password", "-s", "svc", "-a", "acct", "-w",
        ]

    def test_missing_entry_returns_none(self):
        result = MagicMock(returncode=44, stdout="")
        with patch("morning_report.keychain.subprocess.run", return_value=result):
            assert keychain.get_secret("svc", "acct") is None

    def test_empty_value_returns_none(self):
        """An entry holding only whitespace is as useless as no entry at all."""
        result = MagicMock(returncode=0, stdout="  \n")
        with patch("morning_report.keychain.subprocess.run", return_value=result):
            assert keychain.get_secret("svc", "acct") is None


class TestSetSecret:
    def test_deletes_then_adds(self):
        calls = [MagicMock(returncode=0), MagicMock(returncode=0, stderr="")]
        with patch("morning_report.keychain.subprocess.run", side_effect=calls) as mock_run:
            keychain.set_secret("svc", "acct", "val")

        assert mock_run.call_args_list[0][0][0] == [
            "security", "delete-generic-password", "-s", "svc", "-a", "acct",
        ]
        assert mock_run.call_args_list[1][0][0] == [
            "security", "add-generic-password", "-s", "svc", "-a", "acct", "-w", "val",
        ]

    def test_raises_when_add_fails(self):
        calls = [MagicMock(returncode=0), MagicMock(returncode=1, stderr="denied")]
        with patch("morning_report.keychain.subprocess.run", side_effect=calls):
            with pytest.raises(RuntimeError, match="denied"):
                keychain.set_secret("svc", "acct", "val")


class TestClaudeToken:
    def test_get_uses_the_claude_service_and_account(self):
        with patch("morning_report.keychain.get_secret", return_value="tok") as mock_get:
            assert keychain.get_claude_token() == "tok"

        mock_get.assert_called_once_with(
            keychain.CLAUDE_TOKEN_SERVICE, keychain.CLAUDE_TOKEN_ACCOUNT,
        )

    def test_set_uses_the_claude_service_and_account(self):
        with patch("morning_report.keychain.set_secret") as mock_set:
            keychain.set_claude_token("tok")

        mock_set.assert_called_once_with(
            keychain.CLAUDE_TOKEN_SERVICE, keychain.CLAUDE_TOKEN_ACCOUNT, "tok",
        )

    def test_service_name_is_distinct_from_gmail(self):
        assert keychain.CLAUDE_TOKEN_SERVICE != keychain.GMAIL_SERVICE
