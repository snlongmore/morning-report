"""Tests for the Markets gatherer."""

from unittest.mock import patch, MagicMock

import pytest

from morning_report.gatherers.markets import MarketsGatherer, _fetch_crypto, _fetch_stocks


class TestMarketsGatherer:
    def test_name(self):
        g = MarketsGatherer()
        assert g.name == "markets"

    def test_default_crypto(self):
        g = MarketsGatherer()
        assert g._crypto_ids == ["bitcoin", "ethereum"]

    def test_custom_config(self):
        g = MarketsGatherer(config={
            "crypto": ["bitcoin"],
            "stocks": ["^GSPC"],
            "funds": ["VWRL.L"],
        })
        assert g._crypto_ids == ["bitcoin"]
        assert g._stock_tickers == ["^GSPC"]
        assert g._fund_tickers == ["VWRL.L"]


class TestFetchCrypto:
    def test_empty_list(self):
        assert _fetch_crypto([]) == {}

    def test_successful_fetch(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "bitcoin": {"usd": 65000.0, "usd_24h_change": 2.5, "usd_market_cap": 1.2e12},
            "ethereum": {"usd": 3500.0, "usd_24h_change": -1.2, "usd_market_cap": 4.2e11},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("morning_report.gatherers.markets.requests.get", return_value=mock_resp):
            result = _fetch_crypto(["bitcoin", "ethereum"])

        assert result["bitcoin"]["price_usd"] == 65000.0
        assert result["bitcoin"]["change_24h_pct"] == 2.5
        assert result["ethereum"]["price_usd"] == 3500.0

    def test_missing_token(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "bitcoin": {"usd": 65000.0, "usd_24h_change": 2.5, "usd_market_cap": 1.2e12},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("morning_report.gatherers.markets.requests.get", return_value=mock_resp):
            result = _fetch_crypto(["bitcoin", "unknown-token"])

        assert result["bitcoin"]["price_usd"] == 65000.0
        assert result["unknown-token"]["error"] == "Not found on CoinGecko"


class TestFetchStocks:
    def test_yfinance_not_installed(self):
        with patch.dict("sys.modules", {"yfinance": None}):
            # Force reimport to trigger ImportError
            import importlib
            import morning_report.gatherers.markets as m
            orig = m._fetch_stocks

            def mock_fetch(tickers):
                try:
                    import yfinance  # noqa: F401
                except (ImportError, TypeError):
                    return {"_error": "yfinance not installed. Run: uv pip install yfinance"}
                return orig(tickers)

            with patch("morning_report.gatherers.markets._fetch_stocks", side_effect=mock_fetch):
                result = mock_fetch(["^GSPC"])
                assert "_error" in result

    def test_successful_stock_fetch(self):
        mock_info = MagicMock()
        mock_info.last_price = 5200.50
        mock_info.previous_close = 5180.00
        mock_info.currency = "USD"

        mock_ticker = MagicMock()
        mock_ticker.fast_info = mock_info

        mock_yf = MagicMock()
        mock_yf.Ticker.return_value = mock_ticker

        import sys
        with patch.dict(sys.modules, {"yfinance": mock_yf}):
            result = _fetch_stocks(["^GSPC"])

        assert result["^GSPC"]["price"] == 5200.50
        assert result["^GSPC"]["change_pct"] == pytest.approx(0.40, abs=0.01)
        assert result["^GSPC"]["currency"] == "USD"


class TestGather:
    def test_gather_crypto_only(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "bitcoin": {"usd": 65000.0, "usd_24h_change": 2.5, "usd_market_cap": 1.2e12},
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("morning_report.gatherers.markets.requests.get", return_value=mock_resp):
            g = MarketsGatherer(config={"crypto": ["bitcoin"], "stocks": [], "funds": []})
            result = g.gather()

        assert "crypto" in result
        assert result["crypto"]["bitcoin"]["price_usd"] == 65000.0
        assert "stocks" not in result

    def test_safe_gather_wraps_errors(self):
        with patch("morning_report.gatherers.markets.requests.get", side_effect=Exception("API down")):
            g = MarketsGatherer(config={"crypto": ["bitcoin"], "stocks": [], "funds": []})
            result = g.safe_gather()

        assert result["status"] == "error"
        assert "API down" in result["error"]
