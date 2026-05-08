"""
tests/test_stock_api.py – Unit tests for stock_api.py.

All network calls are mocked so tests run completely offline.
Tests cover:
    • Input validation (ValueError for bad symbols)
    • yfinance success path
    • yfinance error → Alpha Vantage fallback
    • Alpha Vantage success path
    • Alpha Vantage missing key error
    • Alpha Vantage HTTP errors and retry logic
    • get_multiple_quotes() – mixed success/failure
    • StockAPIError propagation
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock, PropertyMock

import stock_api
from stock_api import (
    get_stock_quote,
    get_multiple_quotes,
    StockAPIError,
    _fetch_alpha_vantage,
    _fetch_yfinance,
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

def _mock_yf_ticker(price=150.0, prev_close=148.0, volume=1_000_000):
    """Return a MagicMock that mimics yf.Ticker().fast_info."""
    mock_ticker = MagicMock()
    mock_info = MagicMock()
    mock_info.last_price = price
    mock_info.previous_close = prev_close
    mock_info.three_month_average_volume = volume
    mock_ticker.fast_info = mock_info
    return mock_ticker


def _alpha_vantage_response(symbol="AAPL", price="182.50", change="1.25",
                             change_pct="+0.69%", volume="56000000"):
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "05. price": price,
            "09. change": change,
            "10. change percent": change_pct,
            "06. volume": volume,
        }
    }


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_empty_string_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty string"):
            get_stock_quote("")

    def test_whitespace_raises_value_error(self):
        with pytest.raises(ValueError):
            get_stock_quote("   ")

    def test_none_raises_value_error(self):
        with pytest.raises((ValueError, AttributeError)):
            get_stock_quote(None)  # type: ignore[arg-type]

    def test_symbol_is_uppercased(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            mock_yf.Ticker.return_value = _mock_yf_ticker()
            result = get_stock_quote("aapl")
            assert result["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# yfinance path
# ---------------------------------------------------------------------------

class TestYfinancePath:
    def test_successful_quote(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            mock_yf.Ticker.return_value = _mock_yf_ticker(price=182.5, prev_close=181.0)
            result = get_stock_quote("AAPL")
            assert result["symbol"] == "AAPL"
            assert result["price"] == pytest.approx(182.5)
            assert result["source"] == "yfinance"

    def test_change_calculated_correctly(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            mock_yf.Ticker.return_value = _mock_yf_ticker(price=110.0, prev_close=100.0)
            result = get_stock_quote("TSLA")
            assert result["change"] == pytest.approx(10.0)
            assert "10.00%" in result["change_pct"]

    def test_none_price_raises_api_error(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            ticker_mock = MagicMock()
            info_mock = MagicMock()
            info_mock.last_price = None
            ticker_mock.fast_info = info_mock
            mock_yf.Ticker.return_value = ticker_mock
            with pytest.raises(StockAPIError):
                _fetch_yfinance("INVALID")

    def test_yfinance_exception_raises_api_error(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            mock_yf.Ticker.side_effect = RuntimeError("network error")
            with pytest.raises(StockAPIError):
                _fetch_yfinance("AAPL")

    def test_volume_defaults_to_zero_when_none(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            ticker = _mock_yf_ticker(price=100.0, prev_close=99.0, volume=None)
            mock_yf.Ticker.return_value = ticker
            result = _fetch_yfinance("IBM")
            assert result["volume"] == 0

    def test_change_pct_na_when_no_prev_close(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api.yf") as mock_yf:
            ticker = _mock_yf_ticker(price=100.0, prev_close=None)
            mock_yf.Ticker.return_value = ticker
            result = _fetch_yfinance("AAPL")
            assert result["change_pct"] == "N/A"


# ---------------------------------------------------------------------------
# Alpha Vantage path
# ---------------------------------------------------------------------------

class TestAlphaVantagePath:
    def test_successful_quote(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _alpha_vantage_response()
        mock_resp.raise_for_status.return_value = None
        with patch("stock_api.requests.get", return_value=mock_resp), \
             patch.dict("os.environ", {"ALPHA_VANTAGE_KEY": "demo"}):
            result = _fetch_alpha_vantage("AAPL")
            assert result["symbol"] == "AAPL"
            assert result["price"] == pytest.approx(182.50)
            assert result["source"] == "alpha_vantage"

    def test_missing_key_raises_api_error(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove key if set
            import os
            os.environ.pop("ALPHA_VANTAGE_KEY", None)
            with pytest.raises(StockAPIError, match="ALPHA_VANTAGE_KEY"):
                _fetch_alpha_vantage("AAPL")

    def test_empty_global_quote_raises_api_error(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Global Quote": {}}
        mock_resp.raise_for_status.return_value = None
        with patch("stock_api.requests.get", return_value=mock_resp), \
             patch.dict("os.environ", {"ALPHA_VANTAGE_KEY": "demo"}):
            with pytest.raises(StockAPIError, match="No data returned"):
                _fetch_alpha_vantage("UNKNOWN")

    def test_http_error_retries_and_raises(self):
        import requests as req
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = req.HTTPError("503")
        with patch("stock_api.requests.get", return_value=mock_resp), \
             patch("stock_api.time.sleep"), \
             patch.dict("os.environ", {"ALPHA_VANTAGE_KEY": "demo"}):
            with pytest.raises(StockAPIError):
                _fetch_alpha_vantage("AAPL", retries=1)

    def test_volume_parsed_as_int(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _alpha_vantage_response(volume="1234567")
        mock_resp.raise_for_status.return_value = None
        with patch("stock_api.requests.get", return_value=mock_resp), \
             patch.dict("os.environ", {"ALPHA_VANTAGE_KEY": "demo"}):
            result = _fetch_alpha_vantage("AAPL")
            assert isinstance(result["volume"], int)
            assert result["volume"] == 1234567


# ---------------------------------------------------------------------------
# get_stock_quote fallback logic
# ---------------------------------------------------------------------------

class TestFallbackLogic:
    def test_falls_back_to_alpha_vantage_when_yfinance_fails(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = _alpha_vantage_response()
        mock_resp.raise_for_status.return_value = None
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api._fetch_yfinance", side_effect=StockAPIError("yf error")), \
             patch("stock_api._fetch_alpha_vantage", return_value={
                 "symbol": "AAPL", "price": 182.50, "change": 1.25,
                 "change_pct": "+0.69%", "volume": 56000000, "source": "alpha_vantage"
             }), \
             patch("stock_api._alpha_vantage_key", return_value="demo"):
            result = get_stock_quote("AAPL")
            assert result["source"] == "alpha_vantage"

    def test_raises_when_both_backends_fail(self):
        with patch("stock_api._YFINANCE_AVAILABLE", False), \
             patch("stock_api._alpha_vantage_key", return_value=None):
            with pytest.raises(StockAPIError):
                get_stock_quote("AAPL")

    def test_uses_yfinance_when_available(self):
        with patch("stock_api._YFINANCE_AVAILABLE", True), \
             patch("stock_api._fetch_yfinance", return_value={
                 "symbol": "AAPL", "price": 182.50, "change": 1.25,
                 "change_pct": "+0.69%", "volume": 56000000, "source": "yfinance"
             }) as mock_yf:
            result = get_stock_quote("AAPL")
            assert result["source"] == "yfinance"
            mock_yf.assert_called_once_with("AAPL")


# ---------------------------------------------------------------------------
# get_multiple_quotes
# ---------------------------------------------------------------------------

class TestGetMultipleQuotes:
    def test_all_successful(self):
        quotes = {
            "AAPL": {"symbol": "AAPL", "price": 182.50, "change": 1.25,
                     "change_pct": "+0.69%", "volume": 56000000, "source": "yfinance"},
            "TSLA": {"symbol": "TSLA", "price": 250.00, "change": -5.00,
                     "change_pct": "-1.96%", "volume": 30000000, "source": "yfinance"},
        }
        with patch("stock_api.get_stock_quote", side_effect=lambda s: quotes[s]):
            result = get_multiple_quotes(["AAPL", "TSLA"])
            assert "AAPL" in result
            assert "TSLA" in result
            assert result["AAPL"]["price"] == 182.50

    def test_partial_failure(self):
        def side_effect(sym):
            if sym == "INVALID":
                raise StockAPIError("Not found")
            return {"symbol": sym, "price": 100.0, "change": 0.0,
                    "change_pct": "0%", "volume": 0, "source": "yfinance"}

        with patch("stock_api.get_stock_quote", side_effect=side_effect):
            result = get_multiple_quotes(["AAPL", "INVALID"])
            assert "error" in result["INVALID"]
            assert result["AAPL"]["price"] == 100.0

    def test_empty_list(self):
        result = get_multiple_quotes([])
        assert result == {}

    def test_invalid_symbol_in_list(self):
        with patch("stock_api.get_stock_quote", side_effect=ValueError("bad symbol")):
            result = get_multiple_quotes([""])
            assert "error" in result[""]
