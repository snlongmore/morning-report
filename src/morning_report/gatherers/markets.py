"""Markets gatherer — crypto via CoinGecko, stocks/indices via yfinance."""

from __future__ import annotations

import logging
from typing import Any

import requests

from morning_report.gatherers.base import BaseGatherer

logger = logging.getLogger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def _fetch_crypto(token_ids: list[str]) -> dict[str, Any]:
    """Fetch crypto prices from CoinGecko in a single batched call."""
    if not token_ids:
        return {}

    ids_param = ",".join(token_ids)
    resp = requests.get(
        f"{_COINGECKO_BASE}/simple/price",
        params={
            "ids": ids_param,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_market_cap": "true",
        },
        headers={"User-Agent": "MorningReport/0.1.0"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    results = {}
    for token_id in token_ids:
        if token_id in data:
            info = data[token_id]
            results[token_id] = {
                "price_usd": info.get("usd"),
                "change_24h_pct": round(info.get("usd_24h_change", 0), 2),
                "market_cap_usd": info.get("usd_market_cap"),
            }
        else:
            results[token_id] = {"error": "Not found on CoinGecko"}

    return results


def _fetch_stocks(tickers: list[str]) -> dict[str, Any]:
    """Fetch stock/index data via yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        return {"_error": "yfinance not installed. Run: uv pip install yfinance"}

    results = {}
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = getattr(info, "last_price", None)
            prev_close = getattr(info, "previous_close", None)

            if price is None:
                results[ticker] = {"error": f"No data for {ticker}"}
                continue

            change_pct = None
            if price and prev_close and prev_close != 0:
                change_pct = round(((price - prev_close) / prev_close) * 100, 2)

            results[ticker] = {
                "price": round(price, 2),
                "previous_close": round(prev_close, 2) if prev_close else None,
                "change_pct": change_pct,
                "currency": getattr(info, "currency", ""),
            }
        except Exception as e:
            results[ticker] = {"error": str(e)}

    return results


class MarketsGatherer(BaseGatherer):
    """Gathers crypto and stock market data."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._crypto_ids = self._config.get("crypto", ["bitcoin", "ethereum"])
        self._stock_tickers = self._config.get("stocks", [])
        self._fund_tickers = self._config.get("funds", [])

    @property
    def name(self) -> str:
        return "markets"

    def gather(self) -> dict[str, Any]:
        """Fetch crypto and stock data."""
        result: dict[str, Any] = {}

        # Crypto via CoinGecko (single batched call)
        if self._crypto_ids:
            result["crypto"] = _fetch_crypto(self._crypto_ids)

        # Stocks/indices via yfinance
        all_tickers = self._stock_tickers + self._fund_tickers
        if all_tickers:
            stocks = _fetch_stocks(all_tickers)
            if "_error" in stocks:
                result["stocks_error"] = stocks["_error"]
            else:
                result["stocks"] = stocks

        return result
