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

    # Email — accounts is a dict mapping account name to list of messages
    email = data.get("email", {})
    if email.get("status") == "ok":
        accounts = email.get("accounts", {})
        if isinstance(accounts, dict):
            total_unread = sum(len(msgs) for msgs in accounts.values())
            n_accounts = len(accounts)
        else:
            total_unread = 0
            n_accounts = 0
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


def _build_summary_fr(data: dict) -> str:
    """Build a plain-text French summary from gathered JSON data."""
    from morning_report.report.generator import FRENCH_DAYS, FRENCH_MONTHS

    now = datetime.now()
    day_name = FRENCH_DAYS.get(now.strftime("%A"), now.strftime("%A"))
    day_num = now.day
    month_name = FRENCH_MONTHS.get(now.month, str(now.month))

    lines = []
    lines.append(f"Rapport du matin — {day_name} {day_num} {month_name} {now.year}")
    lines.append("")

    # Meteo
    weather = data.get("weather", {})
    if weather.get("status") == "ok":
        for loc_name, loc_data in weather.get("locations", {}).items():
            current = loc_data.get("current", {})
            if current:
                desc = current.get("description", "")
                temp = current.get("temp", "")
                lines.append(f"Meteo : {loc_name} — {desc}, {temp}°C")
                break

    # Agenda
    cal = data.get("calendar", {})
    if cal.get("status") == "ok":
        events = cal.get("events", [])
        today_events = [e for e in events if e.get("start", "").startswith(
            now.strftime("%Y-%m-%d")
        )]
        n_today = len(today_events)
        if today_events:
            first_time = today_events[0].get("start", "")
            if "T" in first_time:
                first_time = first_time.split("T")[1][:5]
            lines.append(f"Agenda : {n_today} evenements aujourd'hui, premier a {first_time}")
        else:
            lines.append(f"Agenda : {n_today} evenements aujourd'hui")

    # Courriels
    email = data.get("email", {})
    if email.get("status") == "ok":
        accounts = email.get("accounts", {})
        if isinstance(accounts, dict):
            total_unread = sum(len(msgs) for msgs in accounts.values())
            n_accounts = len(accounts)
        else:
            total_unread = 0
            n_accounts = 0
        lines.append(f"Courriels : {total_unread} non lus sur {n_accounts} comptes")

    # arXiv
    arxiv = data.get("arxiv", {})
    if arxiv.get("status") == "ok":
        papers = arxiv.get("papers", [])
        n_papers = len(papers)
        lines.append(f"arXiv : {n_papers} nouveaux articles")

    # Marches
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
            lines.append(f"Marches : {', '.join(parts)}")

    lines.append("")
    lines.append("Rapports complets en pieces jointes.")
    return "\n".join(lines)


def _build_subject_fr() -> str:
    """Build a French email subject line."""
    from morning_report.report.generator import FRENCH_DAYS, FRENCH_MONTHS

    now = datetime.now()
    day_name = FRENCH_DAYS.get(now.strftime("%A"), now.strftime("%A"))
    day_num = now.day
    month_name = FRENCH_MONTHS.get(now.month, str(now.month))
    return f"Rapport du matin — {day_name} {day_num} {month_name} {now.year}"


def build_message(
    docx_path: Path,
    json_path: Path,
    recipient: str,
    sender: str,
    docx_fr_path: Path | None = None,
) -> EmailMessage:
    """Build the email message with summary body and .docx attachment(s).

    Args:
        docx_path: Path to the English .docx report file.
        json_path: Path to the gathered data JSON (for summary extraction).
        recipient: Email address to send to.
        sender: Email address to send from.
        docx_fr_path: Optional path to the French .docx report file.

    Returns:
        A fully constructed EmailMessage.
    """
    # Load gathered data for summary
    with open(json_path) as f:
        data = json.load(f)

    # Build message — use French subject and body when French report is available
    msg = EmailMessage()
    if docx_fr_path:
        msg["Subject"] = _build_subject_fr()
        msg.set_content(_build_summary_fr(data))
    else:
        date_str = datetime.now().strftime("%A, %Y-%m-%d")
        msg["Subject"] = f"Morning Report — {date_str}"
        msg.set_content(_build_summary(data))
    msg["From"] = sender
    msg["To"] = recipient

    # Attach English .docx
    docx_bytes = docx_path.read_bytes()
    msg.add_attachment(
        docx_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=docx_path.name,
    )

    # Attach French .docx if provided
    if docx_fr_path:
        docx_fr_bytes = docx_fr_path.read_bytes()
        msg.add_attachment(
            docx_fr_bytes,
            maintype="application",
            subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename=docx_fr_path.name,
        )

    return msg


def send_report(
    docx_path: Path,
    json_path: Path,
    recipient: str,
    sender: str,
    app_password: str | None = None,
    docx_fr_path: Path | None = None,
) -> None:
    """Send morning report via Gmail SMTP with .docx attachment(s) and summary body.

    The app password is resolved in order:
    1. Explicit app_password argument (if provided and not a placeholder)
    2. macOS Keychain (service: morning-report-gmail, account: sender)

    Args:
        docx_path: Path to the English .docx report file.
        json_path: Path to the gathered data JSON (for summary extraction).
        recipient: Email address to send to.
        sender: Email address to send from.
        app_password: Gmail app password. If None, reads from macOS Keychain.
        docx_fr_path: Optional path to the French .docx report file.

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

    msg = build_message(docx_path, json_path, recipient, sender, docx_fr_path=docx_fr_path)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(sender, app_password)
        server.send_message(msg)

    logger.info("Report emailed to %s", recipient)
