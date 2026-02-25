"""Email delivery for morning reports via Gmail SMTP."""

from __future__ import annotations

import json
import logging
import smtplib
import subprocess
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

KEYCHAIN_SERVICE = "morning-report-gmail"


def get_keychain_password(account: str) -> str | None:
    """Read the Gmail app password from macOS Keychain.

    Args:
        account: The account name (email address) stored in Keychain.

    Returns:
        The password string, or None if not found.
    """
    result = subprocess.run(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def set_keychain_password(account: str, password: str) -> None:
    """Store the Gmail app password in macOS Keychain.

    Deletes any existing entry first, then adds the new one.

    Args:
        account: The account name (email address) to store against.
        password: The app password to store.

    Raises:
        RuntimeError: If the Keychain operation fails.
    """
    # Delete existing entry (ignore errors if not found)
    subprocess.run(
        ["security", "delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account],
        capture_output=True,
    )
    result = subprocess.run(
        ["security", "add-generic-password", "-s", KEYCHAIN_SERVICE, "-a", account, "-w", password],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to store password in Keychain: {result.stderr.strip()}")


def _build_summary(data: dict) -> str:
    """Build a plain-text summary from gathered JSON data."""
    lines = []
    date_str = datetime.now().strftime("%A, %Y-%m-%d")
    lines.append(f"Morning Report — {date_str}")
    lines.append("")

    # Weather
    weather = data.get("weather", {})
    if weather.get("status") == "ok":
        for loc_name, loc_data in weather.get("locations", {}).items():
            current = loc_data.get("current", {})
            if current:
                desc = current.get("description", "")
                temp = current.get("temp", "")
                lines.append(f"Weather: {loc_name} — {desc}, {temp}°C")
                break

    # Calendar
    cal = data.get("calendar", {})
    if cal.get("status") == "ok":
        events = cal.get("events", [])
        today_events = [e for e in events if e.get("start", "").startswith(
            datetime.now().strftime("%Y-%m-%d")
        )]
        n_today = len(today_events)
        if today_events:
            first_time = today_events[0].get("start", "")
            if "T" in first_time:
                first_time = first_time.split("T")[1][:5]
            lines.append(f"Calendar: {n_today} events today, first at {first_time}")
        else:
            lines.append(f"Calendar: {n_today} events today")

    # Email
    email = data.get("email", {})
    if email.get("status") == "ok":
        accounts = email.get("accounts", [])
        total_unread = sum(a.get("unread_count", 0) for a in accounts)
        n_accounts = len(accounts)
        lines.append(f"Email: {total_unread} unread across {n_accounts} accounts")

    # arXiv
    arxiv = data.get("arxiv", {})
    if arxiv.get("status") == "ok":
        papers = arxiv.get("papers", [])
        n_papers = len(papers)
        tier1 = sum(1 for p in papers if p.get("tier") == 1)
        tier2 = sum(1 for p in papers if p.get("tier") == 2)
        tier_str = ""
        if tier1 or tier2:
            parts = []
            if tier1:
                parts.append(f"{tier1} tier 1")
            if tier2:
                parts.append(f"{tier2} tier 2")
            tier_str = f" ({', '.join(parts)})"
        lines.append(f"arXiv: {n_papers} new papers{tier_str}")

    # Markets
    markets = data.get("markets", {})
    if markets.get("status") == "ok":
        crypto = markets.get("crypto", {})
        parts = []
        for coin_id, coin_data in crypto.items():
            price = coin_data.get("price_usd")
            symbol = coin_data.get("symbol", coin_id).upper()
            if price is not None:
                if price >= 100:
                    parts.append(f"{symbol} ${price:,.0f}")
                else:
                    parts.append(f"{symbol} ${price:.4f}")
        if parts:
            lines.append(f"Markets: {', '.join(parts)}")

    lines.append("")
    lines.append("Full report attached.")
    return "\n".join(lines)


def build_message(
    docx_path: Path,
    json_path: Path,
    recipient: str,
    sender: str,
) -> EmailMessage:
    """Build the email message with summary body and .docx attachment.

    Args:
        docx_path: Path to the .docx report file.
        json_path: Path to the gathered data JSON (for summary extraction).
        recipient: Email address to send to.
        sender: Email address to send from.

    Returns:
        A fully constructed EmailMessage.
    """
    # Load gathered data for summary
    with open(json_path) as f:
        data = json.load(f)

    # Build message
    msg = EmailMessage()
    date_str = datetime.now().strftime("%A, %Y-%m-%d")
    msg["Subject"] = f"Morning Report — {date_str}"
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(_build_summary(data))

    # Attach .docx
    docx_bytes = docx_path.read_bytes()
    msg.add_attachment(
        docx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )

    return msg


def send_report(
    docx_path: Path,
    json_path: Path,
    recipient: str,
    sender: str,
    app_password: str | None = None,
) -> None:
    """Send morning report via Gmail SMTP with .docx attachment and summary body.

    The app password is resolved in order:
    1. Explicit app_password argument (if provided and not a placeholder)
    2. macOS Keychain (service: morning-report-gmail, account: sender)

    Args:
        docx_path: Path to the .docx report file.
        json_path: Path to the gathered data JSON (for summary extraction).
        recipient: Email address to send to.
        sender: Email address to send from.
        app_password: Gmail app password. If None, reads from macOS Keychain.

    Raises:
        ValueError: If no password can be resolved.
        FileNotFoundError: If docx_path or json_path don't exist.
    """
    # Resolve password: explicit arg → Keychain
    if not app_password or app_password.startswith("${"):
        app_password = get_keychain_password(sender)
    if not app_password:
        raise ValueError(
            "Gmail app password not found. Store it with:\n"
            "  morning-report set-password\n"
            "Generate one at https://myaccount.google.com/apppasswords"
        )

    docx_path = Path(docx_path)
    json_path = Path(json_path)

    if not docx_path.exists():
        raise FileNotFoundError(f"Word document not found: {docx_path}")
    if not json_path.exists():
        raise FileNotFoundError(f"JSON data not found: {json_path}")

    msg = build_message(docx_path, json_path, recipient, sender)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, app_password)
        server.send_message(msg)

    logger.info("Report emailed to %s", recipient)
