"""NASA ADS gatherer — academic metrics with delta tracking."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from morning_report.config import get_project_root
from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_ADS_BASE = "https://api.adsabs.harvard.edu/v1"
_HISTORY_FILE = "ads_history.json"


class ADSGatherer(BaseGatherer):
    """Gathers academic metrics from NASA ADS and tracks deltas."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._token = self._config.get("api_token", "")
        self._author = self._config.get("author") or "longmore, s.n."
        # Allow parent config to pass user.ads_author
        if not self._config.get("author"):
            self._author = "longmore, s.n."

    @property
    def name(self) -> str:
        return "ads"

    def is_available(self) -> bool:
        token = self._token
        if token.startswith("${"):
            return False  # Env var not expanded — not set
        return bool(token)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    def _get_bibcodes(self) -> list[str]:
        """Fetch all bibcodes for the configured author."""
        resp = requests.get(
            f"{_ADS_BASE}/search/query",
            headers=self._headers(),
            params={
                "q": f'author:"{self._author}"',
                "fl": "bibcode",
                "rows": 2000,
                "fq": "database:astronomy",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [doc["bibcode"] for doc in data["response"]["docs"]]

    def _get_metrics(self, bibcodes: list[str]) -> dict[str, Any]:
        """Fetch aggregate metrics for a set of bibcodes."""
        resp = requests.post(
            f"{_ADS_BASE}/metrics",
            headers=self._headers(),
            json={
                "bibcodes": bibcodes,
                "types": ["basic", "citations", "indicators"],
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def _load_history(self) -> dict[str, Any]:
        """Load historical metrics for delta calculation."""
        history_path = get_project_root() / "briefings" / _HISTORY_FILE
        if history_path.exists():
            with open(history_path) as f:
                return json.load(f)
        return {}

    def _save_history(self, metrics: dict[str, Any]):
        """Save current metrics to history file."""
        history_path = get_project_root() / "briefings" / _HISTORY_FILE
        history_path.parent.mkdir(parents=True, exist_ok=True)

        history = self._load_history()
        today = datetime.now().strftime("%Y-%m-%d")
        history[today] = metrics
        with open(history_path, "w") as f:
            json.dump(history, f, indent=2)

    def _compute_deltas(
        self, current: dict[str, Any], history: dict[str, Any]
    ) -> dict[str, Any]:
        """Compare current metrics against the most recent historical entry."""
        if not history:
            return {}

        # Find the most recent date that isn't today
        today = datetime.now().strftime("%Y-%m-%d")
        dates = sorted(d for d in history.keys() if d != today)
        if not dates:
            return {}

        previous = history[dates[-1]]
        prev_date = dates[-1]
        deltas = {"compared_to": prev_date}

        # Compare indicators
        curr_ind = current.get("indicators", {})
        prev_ind = previous.get("indicators", {})
        if curr_ind and prev_ind:
            ind_deltas = {}
            for key in ("h", "g", "m", "i10", "i100", "tori", "riq", "read10"):
                c = curr_ind.get(key)
                p = prev_ind.get(key)
                if c is not None and p is not None:
                    diff = c - p if isinstance(c, (int, float)) else None
                    if diff and diff != 0:
                        ind_deltas[key] = {"current": c, "previous": p, "delta": round(diff, 2)}
            if ind_deltas:
                deltas["indicators"] = ind_deltas

        # Compare citation stats
        curr_cite = current.get("citation stats", {})
        prev_cite = previous.get("citation stats", {})
        if curr_cite and prev_cite:
            cite_deltas = {}
            for key in ("total number of citations", "number of citing papers"):
                c = curr_cite.get(key)
                p = prev_cite.get(key)
                if c is not None and p is not None:
                    diff = c - p
                    if diff != 0:
                        cite_deltas[key] = {"current": c, "previous": p, "delta": diff}
            if cite_deltas:
                deltas["citations"] = cite_deltas

        # Compare basic stats
        curr_basic = current.get("basic stats", {})
        prev_basic = previous.get("basic stats", {})
        if curr_basic and prev_basic:
            papers_c = curr_basic.get("number of papers")
            papers_p = prev_basic.get("number of papers")
            if papers_c is not None and papers_p is not None and papers_c != papers_p:
                deltas["papers"] = {
                    "current": papers_c,
                    "previous": papers_p,
                    "delta": papers_c - papers_p,
                }

        return deltas

    def gather(self) -> dict[str, Any]:
        """Fetch ADS metrics and compute deltas against history."""
        bibcodes = self._get_bibcodes()
        if not bibcodes:
            return {"error": f"No papers found for author '{self._author}'", "status": "error"}

        raw_metrics = self._get_metrics(bibcodes)

        # Extract the key sections
        indicators = raw_metrics.get("indicators", {})
        citation_stats = raw_metrics.get("citation stats", {})
        basic_stats = raw_metrics.get("basic stats", {})

        metrics = {
            "indicators": indicators,
            "citation stats": citation_stats,
            "basic stats": basic_stats,
        }

        # Compute deltas
        history = self._load_history()
        deltas = self._compute_deltas(metrics, history)

        # Save today's metrics
        self._save_history(metrics)

        return {
            "author": self._author,
            "num_bibcodes": len(bibcodes),
            "indicators": indicators,
            "citation_stats": {
                "total_citations": citation_stats.get("total number of citations"),
                "citing_papers": citation_stats.get("number of citing papers"),
                "self_citations": citation_stats.get("number of self-citations"),
            },
            "basic_stats": {
                "total_papers": basic_stats.get("number of papers"),
                "total_reads": basic_stats.get("total number of reads"),
                "recent_reads": basic_stats.get("recent number of reads"),
            },
            "deltas": deltas,
        }
