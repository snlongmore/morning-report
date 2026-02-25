"""CLI entry point using Typer."""

from __future__ import annotations

import json
import logging
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

    _GATHERER_CLASSES["email"] = EmailGatherer
    _GATHERER_CLASSES["calendar"] = CalendarGatherer


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
        # Pass the relevant config section to each gatherer
        gatherer_config = cfg.get(name, {})
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
