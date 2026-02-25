"""arXiv paper tier classification.

Tier 1 — Cites my work: identified via ADS citation search.
Tier 2 — Core research topics: keyword matching for CMZ, star formation, etc.
Tier 3 — COOL project: broader matching for Cosmic Origins of Life topics.
"""

from __future__ import annotations

import re
from typing import Any


def classify_paper(
    title: str,
    abstract: str,
    tier2_keywords: list[str],
    tier3_keywords: list[str],
    citing_bibcodes: set[str] | None = None,
    paper_bibcode: str | None = None,
) -> dict[str, Any]:
    """Classify a paper into a tier.

    Args:
        title: Paper title.
        abstract: Paper abstract.
        tier2_keywords: Keywords for core research topics.
        tier3_keywords: Keywords for COOL project topics.
        citing_bibcodes: Set of bibcodes that cite the user's work (for Tier 1).
        paper_bibcode: This paper's bibcode (if known, for Tier 1 matching).

    Returns:
        Dict with 'tier' (1, 2, 3, or None), 'reason', and 'matched_keywords'.
    """
    # Tier 1: cites my work
    if citing_bibcodes and paper_bibcode and paper_bibcode in citing_bibcodes:
        return {"tier": 1, "reason": "Cites your work", "matched_keywords": []}

    text = (title + " " + abstract).lower()

    # Tier 2: core research topics
    matched_t2 = [kw for kw in tier2_keywords if kw.lower() in text]
    if matched_t2:
        return {"tier": 2, "reason": "Core research topic", "matched_keywords": matched_t2}

    # Tier 3: COOL project
    matched_t3 = [kw for kw in tier3_keywords if kw.lower() in text]
    if matched_t3:
        return {"tier": 3, "reason": "COOL project topic", "matched_keywords": matched_t3}

    return {"tier": None, "reason": "No match", "matched_keywords": []}


def classify_papers(
    papers: list[dict[str, Any]],
    tier2_keywords: list[str],
    tier3_keywords: list[str],
    citing_bibcodes: set[str] | None = None,
) -> dict[int, list[dict[str, Any]]]:
    """Classify a list of papers and group by tier.

    Returns:
        Dict mapping tier number to list of papers with classification info.
    """
    tiers: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}

    for paper in papers:
        result = classify_paper(
            title=paper.get("title", ""),
            abstract=paper.get("abstract", ""),
            tier2_keywords=tier2_keywords,
            tier3_keywords=tier3_keywords,
            citing_bibcodes=citing_bibcodes,
            paper_bibcode=paper.get("bibcode"),
        )
        if result["tier"]:
            enriched = {**paper, **result}
            tiers[result["tier"]].append(enriched)

    return tiers
