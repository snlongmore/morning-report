"""CLI entry point using Typer."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from morning_report.config import get_project_root, load_config

app = typer.Typer(
    name="morning-report",
    help="Automated daily morning briefing system.",
    no_args_is_help=True,
)

# Gatherer registry — maps name to class
_GATHERER_CLASSES = {}


def _register_gatherers():
    """Lazily import and register available gatherers."""
    if _GATHERER_CLASSES:
        return
    from morning_report.gatherers.email import EmailGatherer
    from morning_report.gatherers.calendar import CalendarGatherer
    from morning_report.gatherers.ads import ADSGatherer
    from morning_report.gatherers.arxiv import ArxivGatherer
    from morning_report.gatherers.markets import MarketsGatherer
    from morning_report.gatherers.github import GitHubGatherer
    from morning_report.gatherers.news import NewsGatherer
    from morning_report.gatherers.weather import WeatherGatherer

    _GATHERER_CLASSES["email"] = EmailGatherer
    _GATHERER_CLASSES["calendar"] = CalendarGatherer
    _GATHERER_CLASSES["ads"] = ADSGatherer
    _GATHERER_CLASSES["arxiv"] = ArxivGatherer
    _GATHERER_CLASSES["markets"] = MarketsGatherer
    _GATHERER_CLASSES["github"] = GitHubGatherer
    _GATHERER_CLASSES["news"] = NewsGatherer
    _GATHERER_CLASSES["weather"] = WeatherGatherer


def _setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _gather_french_feeds(cfg: dict) -> dict:
    """Gather French news feeds and meditation feed from config.

    Returns a dict with 'news_fr' and 'meditation' keys, each containing
    gatherer-style results.
    """
    from morning_report.gatherers.news import _parse_feeds

    french_cfg = cfg.get("french", {})
    results = {}

    # French news feeds
    fr_feeds = french_cfg.get("news_feeds", {})
    if fr_feeds:
        try:
            articles = _parse_feeds(fr_feeds, max_per_category=5)
            if "_error" in articles:
                results["news_fr"] = {"status": "error", "error": articles["_error"]}
            else:
                total = sum(len(items) for items in articles.values())
                results["news_fr"] = {
                    "status": "ok",
                    "categories": articles,
                    "total_articles": total,
                }
        except Exception as e:
            results["news_fr"] = {"status": "error", "error": str(e)}
    else:
        results["news_fr"] = {"status": "skipped", "reason": "No French news feeds configured"}

    # Meditation feed (Richard Rohr / CAC)
    meditation_url = french_cfg.get("meditation_feed", "")
    if meditation_url:
        try:
            articles = _parse_feeds({"meditation": [meditation_url]}, max_per_category=1)
            if "_error" in articles:
                results["meditation"] = {"status": "error", "error": articles["_error"]}
            else:
                items = articles.get("meditation", [])
                results["meditation"] = {
                    "status": "ok",
                    "items": items,
                }
        except Exception as e:
            results["meditation"] = {"status": "error", "error": str(e)}
    else:
        results["meditation"] = {"status": "skipped", "reason": "No meditation feed configured"}

    return results


def _should_french(french_flag: bool, cfg: dict) -> bool:
    """Determine whether to generate the French report."""
    if french_flag:
        return True
    return cfg.get("french", {}).get("enabled", False)


@app.command()
def gather(
    only: Optional[str] = typer.Option(
        None, "--only", "-o",
        help="Run only a specific gatherer (e.g. email, calendar).",
    ),
    french: bool = typer.Option(
        False, "--french", "--fr",
        help="Also gather French news feeds and meditation.",
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    output: Optional[Path] = typer.Option(
        None, "--output",
        help="Output directory for gathered data JSON.",
    ),
):
    """Gather data from all configured sources."""
    _setup_logging(verbose)
    logger = logging.getLogger("morning_report")

    cfg = load_config(config_path)
    _register_gatherers()

    # Determine which gatherers to run
    if only:
        names = [n.strip() for n in only.split(",")]
        invalid = [n for n in names if n not in _GATHERER_CLASSES]
        if invalid:
            typer.echo(
                f"Unknown gatherer(s): {', '.join(invalid)}. "
                f"Available: {', '.join(_GATHERER_CLASSES.keys())}",
                err=True,
            )
            raise typer.Exit(1)
    else:
        names = list(_GATHERER_CLASSES.keys())

    # Run gatherers
    results = {}
    for name in names:
        cls = _GATHERER_CLASSES[name]
        gatherer_config = cfg.get(name, {})
        # ArxivGatherer also needs the ADS config for Tier 1 citation checking
        if name == "arxiv":
            gatherer = cls(config=gatherer_config, ads_config=cfg.get("ads", {}))
        else:
            gatherer = cls(config=gatherer_config)
        typer.echo(f"Gathering: {name}...")
        results[name] = gatherer.safe_gather()
        status = results[name].get("status", "unknown")
        if status == "ok":
            typer.echo(f"  {name}: OK")
        else:
            typer.echo(f"  {name}: {status} — {results[name].get('error', results[name].get('reason', ''))}")

    # Gather French feeds if enabled
    if _should_french(french, cfg):
        typer.echo("Gathering: French news feeds...")
        fr_results = _gather_french_feeds(cfg)
        results.update(fr_results)
        for key in ("news_fr", "meditation"):
            status = results.get(key, {}).get("status", "unknown")
            if status == "ok":
                typer.echo(f"  {key}: OK")
            else:
                typer.echo(f"  {key}: {status}")

    # Save raw data
    output_dir = output or (get_project_root() / "briefings")
    from morning_report.report.generator import save_gathered_data
    save_gathered_data(results, output_dir)

    typer.echo(f"\nData saved to {output_dir}/")


@app.command()
def show(
    date: Optional[str] = typer.Option(
        None, "--date", "-d",
        help="Date to show report for (YYYY-MM-DD). Defaults to today.",
    ),
    french: bool = typer.Option(
        False, "--french", "--fr",
        help="Also generate the French report.",
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate and display the morning report."""
    _setup_logging(verbose)

    cfg = load_config(config_path)

    if date:
        report_date = datetime.strptime(date, "%Y-%m-%d")
    else:
        report_date = datetime.now()

    date_str = report_date.strftime("%Y-%m-%d")
    briefings_dir = get_project_root() / "briefings"

    # Check for cached gathered data
    json_path = briefings_dir / f"{date_str}.json"
    if not json_path.exists():
        typer.echo(
            f"No gathered data found for {date_str}. Run 'morning-report gather' first.",
            err=True,
        )
        raise typer.Exit(1)

    with open(json_path) as f:
        data = json.load(f)

    from morning_report.report.generator import generate_report

    # Generate English report
    report = generate_report(data, output_dir=briefings_dir, date=report_date)
    typer.echo(report)

    # Generate French report if enabled
    if _should_french(french, cfg):
        report_fr = generate_report(data, output_dir=briefings_dir, date=report_date, language="fr")
        typer.echo(f"\nFrench report written to {briefings_dir}/{date_str}-fr.md")


@app.command()
def run(
    french: bool = typer.Option(
        False, "--french", "--fr",
        help="Also generate the French report.",
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Gather data and immediately show the report (convenience command)."""
    _setup_logging(verbose)

    # Gather
    cfg = load_config(config_path)
    _register_gatherers()

    results = {}
    for name, cls in _GATHERER_CLASSES.items():
        gatherer_config = cfg.get(name, {})
        if name == "arxiv":
            gatherer = cls(config=gatherer_config, ads_config=cfg.get("ads", {}))
        else:
            gatherer = cls(config=gatherer_config)
        typer.echo(f"Gathering: {name}...")
        results[name] = gatherer.safe_gather()
        status = results[name].get("status", "unknown")
        if status != "ok":
            typer.echo(f"  {name}: {status}")

    # Gather French feeds if enabled
    if _should_french(french, cfg):
        typer.echo("Gathering: French news feeds...")
        fr_results = _gather_french_feeds(cfg)
        results.update(fr_results)

    # Save and render
    briefings_dir = get_project_root() / "briefings"
    from morning_report.report.generator import save_gathered_data, generate_report
    save_gathered_data(results, briefings_dir)
    report = generate_report(results, output_dir=briefings_dir)
    typer.echo("\n" + report)

    # French report
    if _should_french(french, cfg):
        generate_report(results, output_dir=briefings_dir, language="fr")
        date_str = datetime.now().strftime("%Y-%m-%d")
        typer.echo(f"\nFrench report written to {briefings_dir}/{date_str}-fr.md")


@app.command()
def export(
    date: Optional[str] = typer.Option(
        None, "--date", "-d",
        help="Date to export (YYYY-MM-DD). Defaults to today.",
    ),
    french: bool = typer.Option(
        False, "--french", "--fr",
        help="Also export the French report.",
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Export the markdown report to a Word document (.docx) via pandoc."""
    _setup_logging(verbose)

    cfg = load_config(config_path)
    date_str = date or datetime.now().strftime("%Y-%m-%d")
    briefings_dir = get_project_root() / "briefings"
    md_path = briefings_dir / f"{date_str}.md"

    if not md_path.exists():
        typer.echo(
            f"No markdown report found for {date_str}. Run 'morning-report show' first.",
            err=True,
        )
        raise typer.Exit(1)

    from morning_report.report.exporter import export_docx
    docx_path = export_docx(md_path)
    typer.echo(f"Exported: {docx_path}")

    # Export French report if enabled
    if _should_french(french, cfg):
        md_fr_path = briefings_dir / f"{date_str}-fr.md"
        if md_fr_path.exists():
            docx_fr_path = export_docx(md_fr_path)
            typer.echo(f"Exported: {docx_fr_path}")
        else:
            typer.echo(f"No French markdown report found for {date_str}. Skipping French export.")


@app.command()
def email(
    date: Optional[str] = typer.Option(
        None, "--date", "-d",
        help="Date to email (YYYY-MM-DD). Defaults to today.",
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Email the morning report (.docx) with a summary body."""
    _setup_logging(verbose)

    date_str = date or datetime.now().strftime("%Y-%m-%d")
    briefings_dir = get_project_root() / "briefings"
    docx_path = briefings_dir / f"{date_str}.docx"
    json_path = briefings_dir / f"{date_str}.json"

    if not docx_path.exists():
        typer.echo(
            f"No .docx report found for {date_str}. Run 'morning-report export' first.",
            err=True,
        )
        raise typer.Exit(1)

    cfg = load_config(config_path)
    email_cfg = cfg.get("automation", {}).get("email", {})

    # Check for French .docx
    docx_fr_path = briefings_dir / f"{date_str}-fr.docx"
    fr_path = docx_fr_path if docx_fr_path.exists() else None

    from morning_report.report.emailer import send_report
    send_report(
        docx_path=docx_path,
        json_path=json_path,
        recipient=email_cfg.get("recipient", "snlongmore@gmail.com"),
        sender=email_cfg.get("sender", "snlongmore@gmail.com"),
        docx_fr_path=fr_path,
    )
    typer.echo(f"Report emailed to {email_cfg.get('recipient', 'snlongmore@gmail.com')}")


@app.command()
def auto(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Run the full pipeline: gather → show → export → email."""
    _setup_logging(verbose)
    logger = logging.getLogger("morning_report")

    date_str = datetime.now().strftime("%Y-%m-%d")
    briefings_dir = get_project_root() / "briefings"

    # Step 1: Gather
    typer.echo("=== Step 1/4: Gathering data ===")
    cfg = load_config(config_path)
    _register_gatherers()

    results = {}
    for name, cls in _GATHERER_CLASSES.items():
        gatherer_config = cfg.get(name, {})
        if name == "arxiv":
            gatherer = cls(config=gatherer_config, ads_config=cfg.get("ads", {}))
        else:
            gatherer = cls(config=gatherer_config)
        typer.echo(f"  Gathering: {name}...")
        results[name] = gatherer.safe_gather()
        status = results[name].get("status", "unknown")
        if status == "ok":
            typer.echo(f"    {name}: OK")
        else:
            typer.echo(f"    {name}: {status}")

    # Gather French feeds if enabled
    do_french = _should_french(False, cfg)
    if do_french:
        typer.echo("  Gathering: French news feeds...")
        fr_results = _gather_french_feeds(cfg)
        results.update(fr_results)
        for key in ("news_fr", "meditation"):
            status = results.get(key, {}).get("status", "unknown")
            typer.echo(f"    {key}: {status}")

    from morning_report.report.generator import save_gathered_data, generate_report
    save_gathered_data(results, briefings_dir)
    typer.echo(f"  Data saved to {briefings_dir}/{date_str}.json")

    # Step 2: Show (render markdown)
    typer.echo("\n=== Step 2/4: Rendering markdown ===")
    report = generate_report(results, output_dir=briefings_dir)
    typer.echo(f"  Report written to {briefings_dir}/{date_str}.md")

    if do_french:
        generate_report(results, output_dir=briefings_dir, language="fr")
        typer.echo(f"  French report written to {briefings_dir}/{date_str}-fr.md")

    # Step 3: Export to .docx
    typer.echo("\n=== Step 3/4: Exporting to Word ===")
    md_path = briefings_dir / f"{date_str}.md"
    docx_fr_path = None
    try:
        from morning_report.report.exporter import export_docx
        docx_path = export_docx(md_path)
        typer.echo(f"  Exported: {docx_path}")

        if do_french:
            md_fr_path = briefings_dir / f"{date_str}-fr.md"
            if md_fr_path.exists():
                docx_fr_path = export_docx(md_fr_path)
                typer.echo(f"  Exported: {docx_fr_path}")
    except (RuntimeError, FileNotFoundError, OSError) as e:
        typer.echo(f"  Export failed: {e}", err=True)
        typer.echo("  Report is still available as markdown.")
        docx_path = None

    # Step 4: Email
    typer.echo("\n=== Step 4/4: Emailing report ===")
    email_cfg = cfg.get("automation", {}).get("email", {})

    if docx_path is None:
        typer.echo("  Skipping email: no .docx file to attach (export failed).")
        typer.echo("  Report available locally:")
        typer.echo(f"    Markdown: {briefings_dir}/{date_str}.md")
    else:
        try:
            from morning_report.report.emailer import send_report
            json_path = briefings_dir / f"{date_str}.json"
            send_report(
                docx_path=docx_path,
                json_path=json_path,
                recipient=email_cfg.get("recipient", "snlongmore@gmail.com"),
                sender=email_cfg.get("sender", "snlongmore@gmail.com"),
                docx_fr_path=docx_fr_path,
            )
            typer.echo(f"  Report emailed to {email_cfg.get('recipient', 'snlongmore@gmail.com')}")
        except ValueError as e:
            typer.echo(f"  Skipping email: {e}", err=True)
            typer.echo("  Report available locally:")
            typer.echo(f"    Markdown: {briefings_dir}/{date_str}.md")
            typer.echo(f"    Word:     {docx_path}")
        except Exception as e:
            typer.echo(f"  Email failed: {e}", err=True)
            typer.echo("  Report available locally:")
            typer.echo(f"    Markdown: {briefings_dir}/{date_str}.md")
            typer.echo(f"    Word:     {docx_path}")

    typer.echo("\nDone.")


@app.command(name="set-password")
def set_password(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
):
    """Store the Gmail app password in macOS Keychain."""
    cfg = load_config(config_path)
    email_cfg = cfg.get("automation", {}).get("email", {})
    account = email_cfg.get("sender", "snlongmore@gmail.com")

    typer.echo(f"Storing Gmail app password for {account} in macOS Keychain.")
    typer.echo("Generate an app password at: https://myaccount.google.com/apppasswords")
    password = typer.prompt("App password", hide_input=True)

    if not password.strip():
        typer.echo("Password cannot be empty.", err=True)
        raise typer.Exit(1)

    from morning_report.report.emailer import set_keychain_password
    set_keychain_password(account, password.strip())
    typer.echo(f"Password stored in Keychain (service: morning-report-gmail, account: {account})")


_PLIST_LABEL = "com.snl.morning-report"
_PLIST_SOURCE = get_project_root() / "config" / "com.snl.morning-report.plist"
_PLIST_DEST = Path.home() / "Library" / "LaunchAgents" / "com.snl.morning-report.plist"


@app.command(name="install-schedule")
def install_schedule(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Install the daily 05:00 schedule (launchd + pmset wake at 04:55)."""
    _setup_logging(verbose)

    # Symlink plist to ~/Library/LaunchAgents/
    _PLIST_DEST.parent.mkdir(parents=True, exist_ok=True)
    if _PLIST_DEST.exists() or _PLIST_DEST.is_symlink():
        _PLIST_DEST.unlink()
    _PLIST_DEST.symlink_to(_PLIST_SOURCE)
    typer.echo(f"Plist symlinked: {_PLIST_DEST} → {_PLIST_SOURCE}")

    # Load via launchctl
    subprocess.run(["launchctl", "bootout", f"gui/{_get_uid()}", str(_PLIST_DEST)],
                    capture_output=True)  # ignore error if not loaded
    result = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{_get_uid()}", str(_PLIST_DEST)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        typer.echo(f"launchctl bootstrap failed: {result.stderr.strip()}", err=True)
        raise typer.Exit(1)
    typer.echo(f"launchd job loaded: {_PLIST_LABEL}")

    # Set pmset wake schedule (requires sudo)
    typer.echo("\nSetting daily wake at 04:55 (requires sudo):")
    result = subprocess.run(
        ["sudo", "pmset", "repeat", "wakeorpoweron", "MTWRFSU", "04:55:00"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        typer.echo(f"pmset failed: {result.stderr.strip()}", err=True)
        typer.echo("You can set it manually: sudo pmset repeat wakeorpoweron MTWRFSU 04:55:00")
    else:
        typer.echo("pmset wake scheduled: daily at 04:55")

    typer.echo("\nSchedule installed. Check with:")
    typer.echo(f"  launchctl list | grep {_PLIST_LABEL}")
    typer.echo("  pmset -g sched")


@app.command(name="uninstall-schedule")
def uninstall_schedule(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Remove the daily schedule (unload launchd job, clear pmset wake)."""
    _setup_logging(verbose)

    # Unload launchd job
    if _PLIST_DEST.exists() or _PLIST_DEST.is_symlink():
        subprocess.run(
            ["launchctl", "bootout", f"gui/{_get_uid()}", str(_PLIST_DEST)],
            capture_output=True, text=True,
        )
        _PLIST_DEST.unlink()
        typer.echo(f"launchd job unloaded and plist removed: {_PLIST_DEST}")
    else:
        typer.echo("No plist found — launchd job was not installed.")

    # Clear pmset repeat schedule (requires sudo)
    typer.echo("\nClearing pmset wake schedule (requires sudo):")
    result = subprocess.run(
        ["sudo", "pmset", "repeat", "cancel"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        typer.echo(f"pmset cancel failed: {result.stderr.strip()}", err=True)
        typer.echo("You can clear it manually: sudo pmset repeat cancel")
    else:
        typer.echo("pmset wake schedule cleared.")

    typer.echo("\nSchedule removed.")


def _get_uid() -> int:
    """Get the current user's UID for launchctl domain targeting."""
    import os
    return os.getuid()
