"""PDF download handler for arXiv papers."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


def download_pdfs(
    papers: list[dict[str, Any]],
    base_dir: Path | str,
    timeout: int = 30,
) -> int:
    """Download PDFs for a list of papers.

    Papers are saved to base_dir/YYYY-MM-DD/arxiv_id.pdf.

    Args:
        papers: List of paper dicts with 'arxiv_id' and 'pdf_url' keys.
        base_dir: Root directory for paper storage.
        timeout: HTTP timeout per download.

    Returns:
        Number of papers successfully downloaded.
    """
    today_dir = Path(base_dir) / date.today().strftime("%Y-%m-%d")
    today_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    for paper in papers:
        arxiv_id = paper.get("arxiv_id", "")
        pdf_url = paper.get("pdf_url", "")
        if not arxiv_id or not pdf_url:
            continue

        # Sanitise ID for filename (replace / with _)
        filename = arxiv_id.replace("/", "_") + ".pdf"
        filepath = today_dir / filename

        if filepath.exists():
            logger.debug("PDF already exists: %s", filepath)
            downloaded += 1
            continue

        try:
            resp = requests.get(
                pdf_url,
                headers={"User-Agent": "MorningReport/0.1.0"},
                timeout=timeout,
                stream=True,
            )
            resp.raise_for_status()

            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)

            logger.info("Downloaded: %s -> %s", arxiv_id, filepath)
            downloaded += 1

        except Exception as e:
            logger.warning("Failed to download %s: %s", arxiv_id, e)

    return downloaded
