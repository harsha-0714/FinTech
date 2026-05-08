"""
stock_api.py – Real-time stock data integration.

Supports two back-ends:
  1. yfinance  (free, no key required) – primary
  2. Alpha Vantage (free tier, API key via ALPHA_VANTAGE_KEY env var) – fallback
"""

from __future__ import annotations

import os
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional heavy import – yfinance may not be installed in all environments
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
    _YFINANCE_AVAILABLE = True
except ImportError:          # pragma: no cover
    _YFINANCE_AVAILABLE = False
    yf = None                # type: ignore

ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
REQUEST_TIMEOUT = 10  # seconds


class StockAPIError(Exception):
    """Raised when a stock data request fails after all retries."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _alpha_vantage_key() -> Optional[str]:
    return os.environ.get("ALPHA_VANTAGE_KEY")


def _fetch_alpha_vantage(symbol: str, retries: int = 2) -> dict:
    """Fetch a global quote from Alpha Vantage with simple retry logic."""
    key = _alpha_vantage_key()
    if not key:
        raise StockAPIError("ALPHA_VANTAGE_KEY environment variable not set.")

    params = {
        "function": "GLOBAL_QUOTE",
        "symbol": symbol.upper(),
        "apikey": key,
    }
    last_exc: Exception = StockAPIError("Unknown error")
    for attempt in range(1, retries + 2):
        try:
            resp = requests.get(ALPHA_VANTAGE_BASE, params=params,
                                timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
            if "Global Quote" not in data or not data["Global Quote"]:
                raise StockAPIError(
                    f"No data returned for symbol '{symbol}'. "
                    "It may be invalid or the free API limit has been reached."
                )
            quote = data["Global Quote"]
            return {
                "symbol": quote.get("01. symbol", symbol).upper(),
                "price": float(quote.get("05. price", 0)),
                "change": float(quote.get("09. change", 0)),
                "change_pct": quote.get("10. change percent", "0%").strip(),
                "volume": int(quote.get("06. volume", 0)),
                "source": "alpha_vantage",
            }
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_exc = exc
            logger.warning("Alpha Vantage attempt %d failed: %s", attempt, exc)
            if attempt <= retries:
                time.sleep(1)
    raise StockAPIError(f"Alpha Vantage request failed: {last_exc}") from last_exc


def _fetch_yfinance(symbol: str) -> dict:
    """Fetch the latest quote using yfinance."""
    if not _YFINANCE_AVAILABLE:
        raise StockAPIError("yfinance is not installed.")
    try:
        ticker = yf.Ticker(symbol.upper())
        info = ticker.fast_info
        price = getattr(info, "last_price", None)
        prev_close = getattr(info, "previous_close", None)
        if price is None:
            raise StockAPIError(
                f"yfinance returned no price for '{symbol}'. "
                "The symbol may be invalid."
            )
        change = (price - prev_close) if prev_close else 0.0
        change_pct = (
            f"{(change / prev_close * 100):.2f}%"
            if prev_close
            else "N/A"
        )
        return {
            "symbol": symbol.upper(),
            "price": round(float(price), 4),
            "change": round(float(change), 4),
            "change_pct": change_pct,
            "volume": int(getattr(info, "three_month_average_volume", 0) or 0),
            "source": "yfinance",
        }
    except StockAPIError:
        raise
    except Exception as exc:
        raise StockAPIError(f"yfinance error for '{symbol}': {exc}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_stock_quote(symbol: str) -> dict:
    """
    Return the latest quote for *symbol*.

    Tries yfinance first (no key needed).  Falls back to Alpha Vantage if
    yfinance is unavailable or raises an error and an API key is configured.

    Returns a dict with keys:
        symbol, price, change, change_pct, volume, source

    Raises:
        StockAPIError  – if every back-end fails.
        ValueError     – if *symbol* is empty or non-string.
    """
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string.")
    symbol = symbol.strip().upper()

    # --- primary: yfinance ---
    if _YFINANCE_AVAILABLE:
        try:
            return _fetch_yfinance(symbol)
        except StockAPIError as exc:
            logger.info("yfinance failed (%s); trying Alpha Vantage.", exc)

    # --- fallback: Alpha Vantage ---
    if _alpha_vantage_key():
        return _fetch_alpha_vantage(symbol)

    raise StockAPIError(
        f"Could not fetch data for '{symbol}'. "
        "Ensure yfinance is installed or ALPHA_VANTAGE_KEY is set."
    )


def get_multiple_quotes(symbols: list[str]) -> dict[str, dict]:
    """
    Fetch quotes for a list of symbols.

    Returns a dict mapping symbol -> quote dict.
    Failed symbols are mapped to ``{"error": "<message>"}``.
    """
    results: dict[str, dict] = {}
    for sym in symbols:
        try:
            results[sym.upper()] = get_stock_quote(sym)
        except (StockAPIError, ValueError) as exc:
            results[sym.upper()] = {"error": str(exc)}
    return results
