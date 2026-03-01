"""Report generator — renders the French learning document from gathered data."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# French day and month names for date formatting
FRENCH_DAYS = {
    "Monday": "lundi",
    "Tuesday": "mardi",
    "Wednesday": "mercredi",
    "Thursday": "jeudi",
    "Friday": "vendredi",
    "Saturday": "samedi",
    "Sunday": "dimanche",
}

FRENCH_MONTHS = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}

WEATHER_FR = {
    "clear sky": "ciel degage",
    "few clouds": "quelques nuages",
    "scattered clouds": "nuages epars",
    "broken clouds": "nuages fragmentes",
    "overcast clouds": "ciel couvert",
    "shower rain": "averses",
    "rain": "pluie",
    "light rain": "pluie legere",
    "moderate rain": "pluie moderee",
    "heavy intensity rain": "forte pluie",
    "thunderstorm": "orage",
    "snow": "neige",
    "light snow": "neige legere",
    "mist": "brume",
    "fog": "brouillard",
    "haze": "brume seche",
    "drizzle": "bruine",
    "light intensity drizzle": "bruine legere",
}


def french_date(date: datetime) -> str:
    """Format a date in French: 'jeudi 26 fevrier 2026'."""
    day_name = FRENCH_DAYS[date.strftime("%A")]
    day_num = date.day
    month_name = FRENCH_MONTHS[date.month]
    year = date.year
    return f"{day_name} {day_num} {month_name} {year}"


def _weather_fr(description: str) -> str:
    """Translate a weather description to French, falling back to original."""
    return WEATHER_FR.get(description.lower(), description)


def generate_report(
    data: dict[str, Any],
    output_dir: Path | None = None,
    date: datetime | None = None,
    french_content: dict[str, Any] | None = None,
) -> str:
    """Generate the French learning document from gathered data.

    Args:
        data: Dictionary mapping gatherer names to their results.
        output_dir: Directory to write the report file. Defaults to briefings/.
        date: Date for the report. Defaults to today.
        french_content: Dict of AI-generated French content (from french_gen).

    Returns:
        The rendered report as a string.
    """
    from morning_report.french_gen import _FALLBACK_MSG

    date = date or datetime.now()
    date_str = date.strftime("%Y-%m-%d")

    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["weather_fr"] = _weather_fr

    template = env.get_template("french_learning.md.j2")

    rendered = template.render(
        date=date_str,
        date_fr=french_date(date),
        generated_at=datetime.now().strftime("%H:%M"),
        data=data,
        french_content=french_content or {},
        fallback_msg=_FALLBACK_MSG,
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
