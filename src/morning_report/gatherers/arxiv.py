"""arXiv gatherer — new papers with tier classification."""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

import requests

from morning_report.arxiv.classifier import classify_papers
from morning_report.arxiv.paper_handler import download_pdfs
from morning_report.config import get_project_root
from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_ARXIV_API = "https://export.arxiv.org/api/query"
_ADS_BASE = "https://api.adsabs.harvard.edu/v1"

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def _parse_arxiv_entries(xml_text: str) -> list[dict[str, Any]]:
    """Parse arXiv Atom XML into a list of paper dicts."""
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall("atom:entry", _NS):
        # Extract arXiv ID from the <id> URL
        raw_id = entry.find("atom:id", _NS).text
        arxiv_id = raw_id.split("/abs/")[-1]
        # Strip version suffix for canonical ID
        canonical_id = arxiv_id.rsplit("v", 1)[0] if "v" in arxiv_id else arxiv_id

        title = entry.find("atom:title", _NS).text.strip().replace("\n", " ")
        abstract = entry.find("atom:summary", _NS).text.strip()
        published = entry.find("atom:published", _NS).text
        updated = entry.find("atom:updated", _NS).text

        authors = [
            a.find("atom:name", _NS).text
            for a in entry.findall("atom:author", _NS)
        ]

        categories = [
            c.get("term") for c in entry.findall("atom:category", _NS)
        ]
        primary_el = entry.find("arxiv:primary_category", _NS)
        primary_category = primary_el.get("term") if primary_el is not None else ""

        comment_el = entry.find("arxiv:comment", _NS)
        comment = comment_el.text if comment_el is not None else ""

        papers.append({
            "arxiv_id": canonical_id,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "categories": categories,
            "primary_category": primary_category,
            "published": published,
            "updated": updated,
            "comment": comment,
            "abs_url": f"https://arxiv.org/abs/{canonical_id}",
            "pdf_url": f"https://arxiv.org/pdf/{canonical_id}",
        })

    return papers


def _fetch_arxiv_papers(
    categories: list[str],
    lookback_days: int = 1,
    max_results: int = 200,
) -> list[dict[str, Any]]:
    """Fetch recent papers from arXiv across multiple categories."""
    yesterday = date.today() - timedelta(days=lookback_days)
    today = date.today()
    date_from = yesterday.strftime("%Y%m%d") + "000000"
    date_to = today.strftime("%Y%m%d") + "235959"

    # Build category query: (cat:astro-ph.GA OR cat:astro-ph.SR OR ...)
    cat_query = " OR ".join(f"cat:{cat}" for cat in categories)
    query = f"({cat_query}) AND submittedDate:[{date_from} TO {date_to}]"

    resp = requests.get(
        _ARXIV_API,
        params={
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": max_results,
        },
        headers={"User-Agent": "MorningReport/0.1.0"},
        timeout=30,
    )
    resp.raise_for_status()

    papers = _parse_arxiv_entries(resp.text)

    # Deduplicate by canonical ID (cross-listed papers appear in multiple categories)
    seen = set()
    unique = []
    for p in papers:
        if p["arxiv_id"] not in seen:
            seen.add(p["arxiv_id"])
            unique.append(p)

    return unique


def _fetch_recent_citers(
    ads_token: str, author: str, lookback_days: int = 7
) -> set[str]:
    """Find papers from the last N days that cite any paper by the author.

    Uses ADS citations() operator. Returns a set of citing paper bibcodes.
    Note: new arXiv papers may not be in ADS yet, so we look back 7 days.
    """
    if not ads_token or ads_token.startswith("${"):
        return set()

    cutoff = date.today() - timedelta(days=lookback_days)
    cutoff_str = cutoff.strftime("%Y-%m")

    try:
        resp = requests.get(
            f"{_ADS_BASE}/search/query",
            headers={
                "Authorization": f"Bearer {ads_token}",
                "Content-Type": "application/json",
            },
            params={
                "q": f'citations(author:"{author}") AND pubdate:[{cutoff_str} TO *]',
                "fl": "bibcode,title,author,identifier",
                "rows": 200,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        docs = data.get("response", {}).get("docs", [])

        # Build set of bibcodes and also arXiv IDs (from identifier field)
        citers = set()
        for doc in docs:
            citers.add(doc["bibcode"])
            for ident in doc.get("identifier", []):
                # ADS identifiers include arXiv IDs like "arXiv:2602.12345"
                if ident.startswith("arXiv:"):
                    citers.add(ident.replace("arXiv:", ""))
        return citers

    except Exception as e:
        logger.warning("Failed to fetch citation data from ADS: %s", e)
        return set()


class ArxivGatherer(BaseGatherer):
    """Gathers new arXiv papers and classifies them by tier."""

    def __init__(self, config: dict[str, Any] | None = None, ads_config: dict[str, Any] | None = None):
        self._config = config or {}
        self._ads_config = ads_config or {}
        self._categories = self._config.get("categories", ["astro-ph.GA"])
        self._tier2_keywords = self._config.get("tier2_keywords", [])
        self._tier3_keywords = self._config.get("tier3_keywords", [])
        self._papers_dir = self._config.get("papers_dir", "./papers")

    @property
    def name(self) -> str:
        return "arxiv"

    def gather(self) -> dict[str, Any]:
        """Fetch new papers, classify by tier, download relevant PDFs."""
        # Fetch recent papers from arXiv
        papers = _fetch_arxiv_papers(self._categories)

        if not papers:
            return {
                "total_new": 0,
                "tiers": {"1": [], "2": [], "3": []},
                "categories_searched": self._categories,
            }

        # Check for Tier 1 (papers citing user's work) via ADS
        ads_token = self._ads_config.get("api_token", "")
        ads_author = self._ads_config.get("author") or "longmore, s.n."
        citing_ids = _fetch_recent_citers(ads_token, ads_author)

        # Classify all papers
        tiers = classify_papers(
            papers,
            self._tier2_keywords,
            self._tier3_keywords,
            citing_bibcodes=citing_ids,
        )

        # Download PDFs for Tier 1 and Tier 2 papers
        papers_to_download = tiers[1] + tiers[2]
        if papers_to_download:
            papers_dir = get_project_root() / self._papers_dir
            downloaded = download_pdfs(papers_to_download, papers_dir)
        else:
            downloaded = 0

        # Build summaries for the report
        def _paper_summary(p: dict) -> dict:
            return {
                "arxiv_id": p["arxiv_id"],
                "title": p["title"],
                "authors": p["authors"][:5],  # First 5 authors
                "author_count": len(p["authors"]),
                "primary_category": p["primary_category"],
                "abs_url": p["abs_url"],
                "tier": p["tier"],
                "reason": p["reason"],
                "matched_keywords": p.get("matched_keywords", []),
            }

        return {
            "total_new": len(papers),
            "tiers": {
                "1": [_paper_summary(p) for p in tiers[1]],
                "2": [_paper_summary(p) for p in tiers[2]],
                "3": [_paper_summary(p) for p in tiers[3]],
            },
            "tier_counts": {
                "1": len(tiers[1]),
                "2": len(tiers[2]),
                "3": len(tiers[3]),
            },
            "categories_searched": self._categories,
            "pdfs_downloaded": downloaded,
            "ads_citations_available": bool(citing_ids),
        }
