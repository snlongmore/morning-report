"""Export markdown reports to Word documents via pandoc."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def export_docx(md_path: Path, output_path: Path | None = None) -> Path:
    """Convert a markdown report to a Word document via pandoc.

    Args:
        md_path: Path to the markdown file.
        output_path: Where to write the .docx. Defaults to md_path with .docx suffix.

    Returns:
        Path to the generated .docx file.

    Raises:
        FileNotFoundError: If the markdown file does not exist.
        RuntimeError: If pandoc fails.
    """
    md_path = Path(md_path)
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    if output_path is None:
        output_path = md_path.with_suffix(".docx")
    output_path = Path(output_path)

    result = subprocess.run(
        ["pandoc", str(md_path), "-o", str(output_path), "--from=markdown", "--to=docx"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"pandoc failed (exit {result.returncode}): {result.stderr.strip()}")

    logger.info("Exported %s → %s", md_path.name, output_path.name)
    return output_path
