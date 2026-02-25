"""Apple Mail gatherer via AppleScript."""

from __future__ import annotations

import json
import logging
import subprocess
from typing import Any

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

# AppleScript to fetch unread messages from Apple Mail.
# Uses the application-level unified inbox (not per-account inbox property,
# which fails for some account types like Exchange/IMAP).
# Skips message body content to stay fast — subject + sender is enough for triage.
# Returns JSON array of {account, sender, subject, date_received}.
# Limits to 100 most recent unread to avoid timeout.
_APPLESCRIPT = '''
use AppleScript version "2.4"
use scripting additions

on run
    set allMessages to {}
    tell application "Mail"
        -- Use the unified inbox (application-level property)
        set unreadMsgs to (messages of inbox whose read status is false)
        set msgCount to count of unreadMsgs
        if msgCount > 100 then set msgCount to 100
        repeat with i from 1 to msgCount
            set msg to item i of unreadMsgs
            try
                -- Determine which account this message belongs to
                set acctName to "Unknown"
                try
                    set acctName to name of account of mailbox of msg
                end try
                set msgSender to sender of msg
                set msgSubject to subject of msg
                set msgDate to date received of msg as string
                set end of allMessages to {acctName, msgSender, msgSubject, msgDate}
            on error
                -- Skip messages that can't be read
            end try
        end repeat
    end tell

    -- Convert to JSON manually
    set jsonArray to "["
    set isFirst to true
    repeat with msgData in allMessages
        set {acctName, msgSender, msgSubject, msgDate} to msgData
        -- Escape for JSON
        set acctName to my escapeJSON(acctName)
        set msgSender to my escapeJSON(msgSender)
        set msgSubject to my escapeJSON(msgSubject)
        set msgDate to my escapeJSON(msgDate)
        if not isFirst then set jsonArray to jsonArray & ","
        set jsonArray to jsonArray & "{"
        set jsonArray to jsonArray & "\\"account\\":\\"" & acctName & "\\","
        set jsonArray to jsonArray & "\\"sender\\":\\"" & msgSender & "\\","
        set jsonArray to jsonArray & "\\"subject\\":\\"" & msgSubject & "\\","
        set jsonArray to jsonArray & "\\"date_received\\":\\"" & msgDate & "\\""
        set jsonArray to jsonArray & "}"
        set isFirst to false
    end repeat
    set jsonArray to jsonArray & "]"
    return jsonArray
end run

on escapeJSON(str)
    set str to my replaceText(str, "\\\\", "\\\\\\\\")
    set str to my replaceText(str, "\\"", "\\\\\\"")
    set str to my replaceText(str, return, "\\\\n")
    set str to my replaceText(str, linefeed, "\\\\n")
    set str to my replaceText(str, tab, "\\\\t")
    return str
end escapeJSON

on replaceText(theText, searchStr, replaceStr)
    set tid to AppleScript's text item delimiters
    set AppleScript's text item delimiters to searchStr
    set theItems to text items of theText
    set AppleScript's text item delimiters to replaceStr
    set theText to theItems as text
    set AppleScript's text item delimiters to tid
    return theText
end replaceText
'''

# Action words that suggest a response is needed
_ACTION_INDICATORS = [
    "?", "please", "could you", "can you", "would you", "when will",
    "need", "urgent", "asap", "deadline", "action required", "respond",
    "review", "approve", "confirm", "sign off", "feedback",
]


def _needs_response(subject: str, snippet: str = "") -> bool:
    """Heuristic: does this email likely need a response?"""
    text = (subject + " " + snippet).lower()
    return any(indicator in text for indicator in _ACTION_INDICATORS)


class EmailGatherer(BaseGatherer):
    """Gathers unread emails from Apple Mail via AppleScript."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._vip_senders = [
            s.lower() for s in self._config.get("vip_senders", [])
        ]

    @property
    def name(self) -> str:
        return "email"

    def is_available(self) -> bool:
        """Check that we're on macOS with Mail.app."""
        import platform
        return platform.system() == "Darwin"

    def gather(self) -> dict[str, Any]:
        """Fetch unread emails from all Apple Mail accounts."""
        result = subprocess.run(
            ["osascript", "-e", _APPLESCRIPT],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise RuntimeError(f"AppleScript failed: {result.stderr.strip()}")

        raw = result.stdout.strip()
        if not raw:
            return {"accounts": {}, "total_unread": 0, "needs_response": []}

        messages = json.loads(raw)

        # Group by account
        accounts: dict[str, list[dict]] = {}
        needs_response: list[dict] = []

        for msg in messages:
            account = msg.get("account", "Unknown")
            accounts.setdefault(account, []).append(msg)

            # Flag messages needing response
            is_vip = any(
                vip in msg.get("sender", "").lower()
                for vip in self._vip_senders
            )
            if is_vip or _needs_response(msg.get("subject", "")):
                msg["_needs_response"] = True
                msg["_is_vip"] = is_vip
                needs_response.append(msg)

        return {
            "accounts": accounts,
            "total_unread": len(messages),
            "needs_response": needs_response,
            "account_summary": {
                acct: len(msgs) for acct, msgs in accounts.items()
            },
        }
