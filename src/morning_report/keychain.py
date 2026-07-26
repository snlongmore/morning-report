"""Generic macOS Keychain access for the secrets this pipeline needs.

The report runs unattended from launchd, so every secret it depends on has to
live somewhere a background process can read without a prompt. The login
Keychain does that, and unlike an environment variable in a shell rc file it
survives a machine rebuild only if you deliberately put it back, which is the
behaviour we want for a credential.

Two secrets are stored here:

``morning-report-gmail``
    The Gmail app password used to send the finished report.

``morning-report-claude-token``
    A long-lived Claude Code token produced by ``claude setup-token``. The
    normal OAuth session that ``claude`` keeps in its own Keychain entry has a
    short-lived access token, and refreshing it does not work from a launchd
    job, so an unattended run fails whenever the token happens to have expired
    overnight. A long-lived token has no refresh step at all.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)

GMAIL_SERVICE = "morning-report-gmail"
CLAUDE_TOKEN_SERVICE = "morning-report-claude-token"
CLAUDE_TOKEN_ACCOUNT = "oauth"


def get_secret(service: str, account: str) -> str | None:
    """Read a generic password from the login Keychain.

    Args:
        service: Keychain service name.
        account: Keychain account name.

    Returns:
        The stored secret, or None if there is no such entry or it is empty.
    """
    result = subprocess.run(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def set_secret(service: str, account: str, secret: str) -> None:
    """Store a generic password in the login Keychain, replacing any existing one.

    Args:
        service: Keychain service name.
        account: Keychain account name.
        secret: The value to store.

    Raises:
        RuntimeError: If the Keychain write fails.
    """
    # Remove any existing entry first; `security` will not overwrite in place.
    subprocess.run(
        ["security", "delete-generic-password", "-s", service, "-a", account],
        capture_output=True,
    )
    result = subprocess.run(
        ["security", "add-generic-password", "-s", service, "-a", account, "-w", secret],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to store secret in Keychain: {result.stderr.strip()}")


def get_claude_token() -> str | None:
    """Read the long-lived Claude Code token, if one has been stored."""
    return get_secret(CLAUDE_TOKEN_SERVICE, CLAUDE_TOKEN_ACCOUNT)


def set_claude_token(token: str) -> None:
    """Store the long-lived Claude Code token."""
    set_secret(CLAUDE_TOKEN_SERVICE, CLAUDE_TOKEN_ACCOUNT, token)
