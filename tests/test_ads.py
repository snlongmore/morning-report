"""Tests for the ADS gatherer."""

from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.ads import ADSGatherer


class TestADSGatherer:
    def test_name(self):
        g = ADSGatherer()
        assert g.name == "ads"

    def test_not_available_without_token(self):
        g = ADSGatherer(config={"api_token": "${ADS_API_TOKEN}"})
        assert not g.is_available()

    def test_not_available_empty_token(self):
        g = ADSGatherer(config={"api_token": ""})
        assert not g.is_available()

    def test_available_with_token(self):
        g = ADSGatherer(config={"api_token": "real-token-here"})
        assert g.is_available()

    def test_gather_returns_metrics(self):
        mock_search = MagicMock()
        mock_search.json.return_value = {
            "response": {
                "docs": [
                    {"bibcode": "2024ApJ...111...1L"},
                    {"bibcode": "2023MNRAS.222...2L"},
                ]
            }
        }
        mock_search.raise_for_status = MagicMock()

        mock_metrics = MagicMock()
        mock_metrics.json.return_value = {
            "indicators": {
                "h": 38, "g": 62, "m": 2.71,
                "i10": 82, "i100": 14, "tori": 142.3,
                "riq": 412, "read10": 18.4,
            },
            "citation stats": {
                "total number of citations": 5000,
                "number of citing papers": 4200,
                "number of self-citations": 150,
            },
            "basic stats": {
                "number of papers": 142,
                "total number of reads": 48000,
                "recent number of reads": 1000,
            },
        }
        mock_metrics.raise_for_status = MagicMock()

        def side_effect(*args, **kwargs):
            if "search" in args[0] if args else "search" in kwargs.get("url", ""):
                return mock_search
            return mock_metrics

        with patch("morning_report.gatherers.ads.requests.get", return_value=mock_search), \
             patch("morning_report.gatherers.ads.requests.post", return_value=mock_metrics), \
             patch.object(ADSGatherer, "_load_history", return_value={}), \
             patch.object(ADSGatherer, "_save_history"):
            g = ADSGatherer(config={"api_token": "test-token"})
            result = g.gather()

        assert result["num_bibcodes"] == 2
        assert result["indicators"]["h"] == 38
        assert result["citation_stats"]["total_citations"] == 5000
        assert result["basic_stats"]["total_papers"] == 142

    def test_delta_computation(self):
        g = ADSGatherer(config={"api_token": "test"})
        current = {
            "indicators": {"h": 39, "g": 63, "i10": 83},
            "citation stats": {"total number of citations": 5050},
            "basic stats": {"number of papers": 143},
        }
        history = {
            "2026-02-24": {
                "indicators": {"h": 38, "g": 62, "i10": 82},
                "citation stats": {"total number of citations": 5000},
                "basic stats": {"number of papers": 142},
            }
        }
        deltas = g._compute_deltas(current, history)
        assert deltas["compared_to"] == "2026-02-24"
        assert deltas["indicators"]["h"]["delta"] == 1
        assert deltas["citations"]["total number of citations"]["delta"] == 50
        assert deltas["papers"]["delta"] == 1
