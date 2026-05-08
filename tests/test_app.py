"""
tests/test_app.py – Integration tests for the Flask application (app.py).

Uses Flask's built-in test client so no live server is needed.
All stock API calls are mocked to keep tests offline.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import patch

from app import app as flask_app
from stock_api import StockAPIError


MOCK_QUOTE = {
    "symbol": "AAPL",
    "price": 182.50,
    "change": 1.25,
    "change_pct": "+0.69%",
    "volume": 56_000_000,
    "source": "yfinance",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    with flask_app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

class TestRootEndpoint:
    def test_get_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get("/")
        data = json.loads(resp.data)
        assert "name" in data
        assert data["name"] == "FinTech Chatbot API"

    def test_endpoints_listed(self, client):
        resp = client.get("/")
        data = json.loads(resp.data)
        assert "endpoints" in data


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_ok(self, client):
        data = json.loads(client.get("/health").data)
        assert data["status"] == "ok"


# ---------------------------------------------------------------------------
# /chat endpoint
# ---------------------------------------------------------------------------

class TestChatEndpoint:
    def test_missing_body_returns_400(self, client):
        resp = client.post("/chat", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_missing_query_key_returns_400(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_non_string_query_returns_400(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": 123}),
            content_type="application/json",
        )
        assert resp.status_code == 400

    def test_greeting_returns_200(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "Hello"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert "response" in data
        assert "category" in data

    def test_investment_query(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "How should I invest $10,000?"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["category"] == "investment"

    def test_budgeting_query(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "Help me create a budget"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["category"] == "budgeting"

    def test_crypto_query(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "Tell me about Bitcoin"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["category"] == "crypto"

    @patch("app.get_response")
    def test_stock_query_calls_get_response(self, mock_gr, client):
        mock_gr.return_value = {
            "query": "AAPL stock",
            "category": "stock",
            "response": "AAPL is $182.50",
            "timestamp": "2024-01-01T00:00:00Z",
            "ticker": "AAPL",
        }
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "AAPL stock"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        mock_gr.assert_called_once_with("AAPL stock")

    def test_empty_query_returns_200(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": ""}),
            content_type="application/json",
        )
        assert resp.status_code == 200

    def test_response_has_timestamp(self, client):
        resp = client.post(
            "/chat",
            data=json.dumps({"query": "Hello"}),
            content_type="application/json",
        )
        data = json.loads(resp.data)
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# /stock/<symbol> endpoint
# ---------------------------------------------------------------------------

class TestStockEndpoint:
    @patch("app.get_stock_quote", return_value=MOCK_QUOTE)
    def test_valid_symbol_returns_200(self, mock_quote, client):
        resp = client.get("/stock/AAPL")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["symbol"] == "AAPL"
        assert data["price"] == 182.50

    @patch("app.get_stock_quote", side_effect=StockAPIError("API limit"))
    def test_api_error_returns_502(self, mock_quote, client):
        resp = client.get("/stock/AAPL")
        assert resp.status_code == 502
        data = json.loads(resp.data)
        assert "error" in data

    @patch("app.get_stock_quote", side_effect=ValueError("bad symbol"))
    def test_value_error_returns_400(self, mock_quote, client):
        resp = client.get("/stock/AAPL")
        assert resp.status_code == 400

    @patch("app.get_stock_quote", return_value=MOCK_QUOTE)
    def test_symbol_is_uppercased(self, mock_quote, client):
        resp = client.get("/stock/aapl")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    def test_404_returns_json(self, client):
        resp = client.get("/nonexistent-endpoint")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert "error" in data

    def test_post_to_get_only_endpoint_returns_405(self, client):
        resp = client.post("/health", data="{}", content_type="application/json")
        assert resp.status_code == 405
        data = json.loads(resp.data)
        assert "error" in data
