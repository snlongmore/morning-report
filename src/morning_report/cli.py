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


@app.command()
def gather(
    only: Optional[str] = typer.Option(
        None, "--only", "-o",
        help="Run only a specific gatherer (e.g. email, calendar).",
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
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c",
        help="Path to config file.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Generate and display the morning report."""
    _setup_logging(verbose)

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
    report = generate_report(data, output_dir=briefings_dir, date=report_date)
    typer.echo(report)


@app.command()
def run(
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

    # Save and render
    briefings_dir = get_project_root() / "briefings"
    from morning_report.report.generator import save_gathered_data, generate_report
    save_gathered_data(results, briefings_dir)
    report = generate_report(results, output_dir=briefings_dir)
    typer.echo("\n" + report)


@app.command()
def export(
    date: Optional[str] = typer.Option(
        None, "--date", "-d",
        help="Date to export (YYYY-MM-DD). Defaults to today.",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """Export the markdown report to a Word document (.docx) via pandoc."""
    _setup_logging(verbose)

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

    from morning_report.report.emailer import send_report
    send_report(
        docx_path=docx_path,
        json_path=json_path,
        recipient=email_cfg.get("recipient", "snlongmore@gmail.com"),
        sender=email_cfg.get("sender", "snlongmore@gmail.com"),
        app_password=email_cfg.get("app_password", ""),
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

    from morning_report.report.generator import save_gathered_data, generate_report
    save_gathered_data(results, briefings_dir)
    typer.echo(f"  Data saved to {briefings_dir}/{date_str}.json")

    # Step 2: Show (render markdown)
    typer.echo("\n=== Step 2/4: Rendering markdown ===")
    report = generate_report(results, output_dir=briefings_dir)
    typer.echo(f"  Report written to {briefings_dir}/{date_str}.md")

    # Step 3: Export to .docx
    typer.echo("\n=== Step 3/4: Exporting to Word ===")
    md_path = briefings_dir / f"{date_str}.md"
    try:
        from morning_report.report.exporter import export_docx
        docx_path = export_docx(md_path)
        typer.echo(f"  Exported: {docx_path}")
    except (RuntimeError, FileNotFoundError) as e:
        typer.echo(f"  Export failed: {e}", err=True)
        typer.echo("  Report is still available as markdown.")
        raise typer.Exit(1)

    # Step 4: Email
    typer.echo("\n=== Step 4/4: Emailing report ===")
    email_cfg = cfg.get("automation", {}).get("email", {})
    app_password = email_cfg.get("app_password", "")

    if not app_password or app_password.startswith("${"):
        typer.echo("  Skipping email: GMAIL_APP_PASSWORD not configured.")
        typer.echo("  Report available locally:")
        typer.echo(f"    Markdown: {briefings_dir}/{date_str}.md")
        typer.echo(f"    Word:     {docx_path}")
    else:
        try:
            from morning_report.report.emailer import send_report
            json_path = briefings_dir / f"{date_str}.json"
            send_report(
                docx_path=docx_path,
                json_path=json_path,
                recipient=email_cfg.get("recipient", "snlongmore@gmail.com"),
                sender=email_cfg.get("sender", "snlongmore@gmail.com"),
                app_password=app_password,
            )
            typer.echo(f"  Report emailed to {email_cfg.get('recipient', 'snlongmore@gmail.com')}")
        except Exception as e:
            typer.echo(f"  Email failed: {e}", err=True)
            typer.echo("  Report available locally:")
            typer.echo(f"    Markdown: {briefings_dir}/{date_str}.md")
            typer.echo(f"    Word:     {docx_path}")

    typer.echo("\nDone.")


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
