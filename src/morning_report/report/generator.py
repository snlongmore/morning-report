"""Report generator — assembles gathered data into a structured markdown briefing."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def generate_report(
    data: dict[str, Any],
    output_dir: Path | None = None,
    date: datetime | None = None,
) -> str:
    """Generate a morning report from gathered data.

    Args:
        data: Dictionary mapping gatherer names to their results.
        output_dir: Directory to write the report file. Defaults to briefings/.
        date: Date for the report. Defaults to today.

    Returns:
        The rendered report as a string.
    """
    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    day_name = date.strftime("%A")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("morning_report.md.j2")

    rendered = template.render(
        date=date_str,
        day_name=day_name,
        generated_at=datetime.now().strftime("%H:%M"),
        data=data,
    )

    # Write to file if output_dir specified
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{date_str}.md"
        output_path.write_text(rendered)
        logger.info("Report written to %s", output_path)

    return rendered


def save_gathered_data(data: dict[str, Any], output_dir: Path, date: datetime | None = None):
    """Save raw gathered data as JSON for debugging/caching."""
    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{date_str}.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info("Gathered data saved to %s", output_path)
