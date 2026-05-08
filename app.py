"""
app.py – Flask web application for the FinTech chatbot.

Endpoints
---------
GET  /             – health check / welcome
POST /chat         – process a financial query
GET  /stock/<sym>  – get a live stock quote
GET  /health       – liveness probe (for cloud deployments)
"""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request

from chatbot import get_response
from stock_api import StockAPIError, get_stock_quote

# ---------------------------------------------------------------------------
# Application setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def index():
    """Welcome / root endpoint."""
    return jsonify(
        {
            "name": "FinTech Chatbot API",
            "version": "1.0.0",
            "description": (
                "A financial assistant chatbot supporting stock quotes, "
                "investment guidance, budgeting tips, and cryptocurrency info."
            ),
            "endpoints": {
                "POST /chat": "Submit a financial query. Body: {\"query\": \"...\"}",
                "GET /stock/<symbol>": "Get a live stock quote.",
                "GET /health": "Liveness probe.",
            },
        }
    )


@app.route("/health", methods=["GET"])
def health():
    """Liveness probe used by Heroku / cloud platforms."""
    return jsonify({"status": "ok"}), 200


@app.route("/chat", methods=["POST"])
def chat():
    """
    Process a financial query.

    Expected request body (JSON):
        { "query": "<user question>" }

    Returns 200 with the chatbot response dict, or 400 on bad input.
    """
    data = request.get_json(silent=True)

    if not data or "query" not in data:
        return (
            jsonify(
                {
                    "error": "Request body must be JSON with a 'query' field.",
                    "example": {"query": "What is the price of AAPL?"},
                }
            ),
            400,
        )

    query = data["query"]
    if not isinstance(query, str):
        return jsonify({"error": "'query' must be a string."}), 400

    result = get_response(query)
    return jsonify(result), 200


@app.route("/stock/<symbol>", methods=["GET"])
def stock_quote(symbol: str):
    """
    Return a live stock quote for *symbol*.

    Example: GET /stock/AAPL
    """
    symbol = symbol.strip().upper()
    if not symbol:
        return jsonify({"error": "Symbol cannot be empty."}), 400

    try:
        quote = get_stock_quote(symbol)
        return jsonify(quote), 200
    except ValueError:
        return jsonify({"error": f"Invalid symbol '{symbol}'."}), 400
    except StockAPIError as exc:
        logger.error("StockAPIError for %s: %s", symbol, exc)
        return (
            jsonify({"error": f"Could not retrieve data for '{symbol}'. Please try again later."}),
            502,
        )


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(exc):
    return jsonify({"error": "Endpoint not found."}), 404


@app.errorhandler(405)
def method_not_allowed(exc):
    return jsonify({"error": "Method not allowed."}), 405


@app.errorhandler(500)
def internal_error(exc):
    logger.exception("Unhandled exception: %s", exc)
    return jsonify({"error": "Internal server error."}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
