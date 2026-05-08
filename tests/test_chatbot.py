"""
tests/test_chatbot.py – Unit tests for chatbot.py query logic.

Covers:
    • classify_query()  – all categories including edge cases
    • extract_ticker()  – known and heuristic tickers
    • get_response()    – all categories, empty input
    • Stock API errors are mocked so tests run offline.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

import chatbot
from chatbot import (
    classify_query,
    extract_ticker,
    get_response,
    CATEGORY_STOCK,
    CATEGORY_INVESTMENT,
    CATEGORY_BUDGETING,
    CATEGORY_CRYPTO,
    CATEGORY_GENERAL,
    CATEGORY_GREETING,
    CATEGORY_UNKNOWN,
)
from stock_api import StockAPIError


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MOCK_QUOTE = {
    "symbol": "AAPL",
    "price": 182.50,
    "change": 1.25,
    "change_pct": "+0.69%",
    "volume": 56_000_000,
    "source": "yfinance",
}


# ---------------------------------------------------------------------------
# classify_query tests
# ---------------------------------------------------------------------------

class TestClassifyQuery:
    def test_greeting_hi(self):
        assert classify_query("hi") == CATEGORY_GREETING

    def test_greeting_hello(self):
        assert classify_query("Hello there!") == CATEGORY_GREETING

    def test_greeting_good_morning(self):
        assert classify_query("good morning") == CATEGORY_GREETING

    def test_stock_keyword(self):
        assert classify_query("What is the stock price today?") == CATEGORY_STOCK

    def test_stock_known_ticker(self):
        assert classify_query("Tell me about AAPL") == CATEGORY_STOCK

    def test_stock_nasdaq(self):
        assert classify_query("How is NASDAQ doing?") == CATEGORY_STOCK

    def test_investment_keyword(self):
        assert classify_query("How should I invest my money?") == CATEGORY_INVESTMENT

    def test_investment_etf(self):
        assert classify_query("What are the best ETFs for beginners?") == CATEGORY_INVESTMENT

    def test_investment_portfolio(self):
        assert classify_query("Help me build a portfolio") == CATEGORY_INVESTMENT

    def test_budgeting_expense(self):
        assert classify_query("How can I reduce my expenses?") == CATEGORY_BUDGETING

    def test_budgeting_save(self):
        assert classify_query("Tips for saving money") == CATEGORY_BUDGETING

    def test_budgeting_debt(self):
        assert classify_query("I have a lot of debt, what should I do?") == CATEGORY_BUDGETING

    def test_crypto_bitcoin(self):
        assert classify_query("What is Bitcoin?") == CATEGORY_CRYPTO

    def test_crypto_ethereum(self):
        assert classify_query("Should I buy Ethereum?") == CATEGORY_CRYPTO

    def test_crypto_btc(self):
        assert classify_query("Is BTC a good investment?") == CATEGORY_CRYPTO

    def test_general_finance(self):
        assert classify_query("Tell me about financial planning") == CATEGORY_GENERAL

    def test_general_tax(self):
        assert classify_query("How do taxes work?") == CATEGORY_GENERAL

    def test_unknown_empty(self):
        assert classify_query("") == CATEGORY_UNKNOWN

    def test_unknown_whitespace(self):
        assert classify_query("   ") == CATEGORY_UNKNOWN

    def test_unknown_non_financial(self):
        assert classify_query("What is the weather like today?") == CATEGORY_UNKNOWN

    def test_non_string_input(self):
        assert classify_query(None) == CATEGORY_UNKNOWN  # type: ignore[arg-type]

    def test_non_string_int(self):
        assert classify_query(42) == CATEGORY_UNKNOWN  # type: ignore[arg-type]

    def test_case_insensitive_investment(self):
        assert classify_query("HOW SHOULD I INVEST MY MONEY") == CATEGORY_INVESTMENT

    def test_ipo_classified_as_stock(self):
        assert classify_query("What are the upcoming IPOs?") == CATEGORY_STOCK


# ---------------------------------------------------------------------------
# extract_ticker tests
# ---------------------------------------------------------------------------

class TestExtractTicker:
    def test_known_ticker_aapl(self):
        assert extract_ticker("What is AAPL price?") == "AAPL"

    def test_known_ticker_tsla(self):
        assert extract_ticker("Show me TSLA stock") == "TSLA"

    def test_price_of_pattern(self):
        result = extract_ticker("What is the price of NVDA?")
        assert result == "NVDA"

    def test_stock_suffix_pattern(self):
        result = extract_ticker("MSFT stock is rising")
        assert result == "MSFT"

    def test_no_ticker_returns_none(self):
        assert extract_ticker("How do I save money?") is None

    def test_empty_query(self):
        assert extract_ticker("") is None

    def test_multiple_known_tickers_returns_one(self):
        # Should return a result (alphabetically first known ticker)
        result = extract_ticker("Compare AAPL and MSFT")
        assert result in ("AAPL", "MSFT")


# ---------------------------------------------------------------------------
# get_response tests
# ---------------------------------------------------------------------------

class TestGetResponse:
    def test_empty_query_returns_prompt(self):
        result = get_response("")
        assert result["category"] == CATEGORY_UNKNOWN
        assert "Please enter" in result["response"]
        assert result["ticker"] is None

    def test_whitespace_query(self):
        result = get_response("   ")
        assert result["category"] == CATEGORY_UNKNOWN

    def test_greeting_response(self):
        result = get_response("Hello")
        assert result["category"] == CATEGORY_GREETING
        assert "Hello" in result["response"] or "financial" in result["response"].lower()

    def test_investment_response(self):
        result = get_response("How should I invest my savings?")
        assert result["category"] == CATEGORY_INVESTMENT
        assert result["response"]
        assert "Investment" in result["response"] or "invest" in result["response"].lower()

    def test_budgeting_response(self):
        result = get_response("Give me budgeting tips")
        assert result["category"] == CATEGORY_BUDGETING
        assert result["response"]

    def test_crypto_response(self):
        result = get_response("Tell me about Bitcoin")
        assert result["category"] == CATEGORY_CRYPTO
        assert result["response"]

    def test_general_response(self):
        result = get_response("Tell me about financial planning")
        assert result["category"] == CATEGORY_GENERAL
        assert result["response"]

    def test_unknown_response(self):
        result = get_response("What is the weather?")
        assert result["category"] == CATEGORY_UNKNOWN

    def test_response_has_timestamp(self):
        result = get_response("Hello")
        assert "timestamp" in result
        assert result["timestamp"].endswith("Z")

    def test_response_has_query_field(self):
        result = get_response("Hello")
        assert result["query"] == "Hello"

    @patch("chatbot.get_stock_quote", return_value=MOCK_QUOTE)
    def test_stock_response_with_ticker(self, mock_quote):
        result = get_response("What is the price of AAPL?")
        assert result["category"] == CATEGORY_STOCK
        assert "AAPL" in result["response"]
        assert "182.50" in result["response"]
        mock_quote.assert_called_once_with("AAPL")

    @patch("chatbot.get_stock_quote", side_effect=StockAPIError("API limit reached"))
    def test_stock_response_api_error(self, mock_quote):
        result = get_response("What is the price of AAPL?")
        assert result["category"] == CATEGORY_STOCK
        assert "Could not retrieve" in result["response"]

    @patch("chatbot.get_stock_quote", return_value=MOCK_QUOTE)
    def test_stock_response_sets_ticker(self, mock_quote):
        result = get_response("TSLA stock price")
        assert result["ticker"] is not None

    def test_none_query_handled(self):
        result = get_response(None)  # type: ignore[arg-type]
        assert result["category"] == CATEGORY_UNKNOWN

    @patch("chatbot.get_stock_quote", return_value=MOCK_QUOTE)
    def test_stock_negative_change(self, mock_quote):
        negative_quote = dict(MOCK_QUOTE, change=-2.50, change_pct="-1.35%")
        mock_quote.return_value = negative_quote
        result = get_response("What is the price of AAPL?")
        assert result["category"] == CATEGORY_STOCK
        # Negative change should still produce a valid response
        assert "AAPL" in result["response"]

    def test_query_is_stripped_in_result(self):
        result = get_response("  Hello  ")
        assert result["query"] == "Hello"


# ---------------------------------------------------------------------------
# Accuracy benchmark – 100+ queries must classify correctly (≥95%)
# ---------------------------------------------------------------------------

class TestAccuracyBenchmark:
    """
    Tests that classify_query() handles 100+ labelled queries with ≥95%
    accuracy (i.e., ≤5 misclassifications).
    """

    LABELLED_QUERIES: list[tuple[str, str]] = [
        # Stock queries (20)
        ("What is the price of AAPL?", CATEGORY_STOCK),
        ("Show me TSLA stock", CATEGORY_STOCK),
        ("MSFT share price today", CATEGORY_STOCK),
        ("How is the NASDAQ performing?", CATEGORY_STOCK),
        ("S&P 500 index update", CATEGORY_STOCK),
        ("Current market cap of Apple", CATEGORY_STOCK),
        ("NVDA stock prediction", CATEGORY_STOCK),
        ("AMZN equity analysis", CATEGORY_STOCK),
        ("Buy or sell JPM stock?", CATEGORY_STOCK),
        ("What are the dividends for ORCL?", CATEGORY_STOCK),
        ("Dow Jones today", CATEGORY_STOCK),
        ("NYSE opening time", CATEGORY_STOCK),
        ("GOOGL shares outstanding", CATEGORY_STOCK),
        ("Tell me about META stock", CATEGORY_STOCK),
        ("IBM equity value", CATEGORY_STOCK),
        ("Is V a good stock to buy?", CATEGORY_STOCK),
        ("SPY ETF price", CATEGORY_STOCK),
        ("QQQ performance today", CATEGORY_STOCK),
        ("Upcoming IPOs this month", CATEGORY_STOCK),
        ("AMD stock split history", CATEGORY_STOCK),
        # Investment queries (20)
        ("How should I invest $10,000?", CATEGORY_INVESTMENT),
        ("Best ETFs for beginners", CATEGORY_INVESTMENT),
        ("What is a mutual fund?", CATEGORY_INVESTMENT),
        ("How to diversify my portfolio?", CATEGORY_INVESTMENT),
        ("Explain dollar-cost averaging", CATEGORY_INVESTMENT),
        ("What is a Roth IRA?", CATEGORY_INVESTMENT),
        ("How does a 401k work?", CATEGORY_INVESTMENT),
        ("Asset allocation for retirement", CATEGORY_INVESTMENT),
        ("Index fund vs active fund", CATEGORY_INVESTMENT),
        ("How to rebalance a portfolio?", CATEGORY_INVESTMENT),
        ("What is the risk of bonds?", CATEGORY_INVESTMENT),
        ("Yield on treasury bonds", CATEGORY_INVESTMENT),
        ("How to start investing?", CATEGORY_INVESTMENT),
        ("Return on investment strategies", CATEGORY_INVESTMENT),
        ("Best low-risk investments", CATEGORY_INVESTMENT),
        ("How does compound interest work?", CATEGORY_INVESTMENT),
        ("What percentage to invest monthly?", CATEGORY_INVESTMENT),
        ("IRA contribution limits 2024", CATEGORY_INVESTMENT),
        ("Is real estate a good investment?", CATEGORY_INVESTMENT),
        ("Long-term vs short-term investing", CATEGORY_INVESTMENT),
        # Budgeting queries (20)
        ("How do I create a budget?", CATEGORY_BUDGETING),
        ("Help me reduce my expenses", CATEGORY_BUDGETING),
        ("What is the 50/30/20 rule?", CATEGORY_BUDGETING),
        ("How much should I save each month?", CATEGORY_BUDGETING),
        ("Tips for paying off debt", CATEGORY_BUDGETING),
        ("How to build an emergency fund?", CATEGORY_BUDGETING),
        ("Best apps for expense tracking", CATEGORY_BUDGETING),
        ("How to live below my means?", CATEGORY_BUDGETING),
        ("Zero-based budgeting explained", CATEGORY_BUDGETING),
        ("How to save on bills?", CATEGORY_BUDGETING),
        ("Managing a mortgage payment", CATEGORY_BUDGETING),
        ("Loan repayment strategies", CATEGORY_BUDGETING),
        ("How to increase net worth?", CATEGORY_BUDGETING),
        ("Cash flow management tips", CATEGORY_BUDGETING),
        ("Cutting unnecessary spending", CATEGORY_BUDGETING),
        ("How to negotiate salary?", CATEGORY_BUDGETING),
        ("Income budgeting for freelancers", CATEGORY_BUDGETING),
        ("How to pay off student loans?", CATEGORY_BUDGETING),
        ("Building credit score tips", CATEGORY_BUDGETING),
        ("Saving for a down payment", CATEGORY_BUDGETING),
        # Crypto queries (20)
        ("Is Bitcoin a good investment?", CATEGORY_CRYPTO),
        ("How does Ethereum work?", CATEGORY_CRYPTO),
        ("What is DeFi?", CATEGORY_CRYPTO),
        ("BTC price prediction", CATEGORY_CRYPTO),
        ("ETH vs BTC comparison", CATEGORY_CRYPTO),
        ("How to store cryptocurrency safely?", CATEGORY_CRYPTO),
        ("What are NFTs?", CATEGORY_CRYPTO),
        ("Dogecoin investment advice", CATEGORY_CRYPTO),
        ("Blockchain technology explained", CATEGORY_CRYPTO),
        ("Litecoin vs Bitcoin", CATEGORY_CRYPTO),
        ("What is XRP used for?", CATEGORY_CRYPTO),
        ("Crypto tax implications", CATEGORY_CRYPTO),
        ("Best altcoins to watch", CATEGORY_CRYPTO),
        ("How to buy Ethereum?", CATEGORY_CRYPTO),
        ("What is a crypto wallet?", CATEGORY_CRYPTO),
        ("Ripple price today", CATEGORY_CRYPTO),
        ("DeFi yield farming explained", CATEGORY_CRYPTO),
        ("Bitcoin halving impact", CATEGORY_CRYPTO),
        ("Crypto market volatility", CATEGORY_CRYPTO),
        ("Is crypto regulated?", CATEGORY_CRYPTO),
        # Greetings (10)
        ("hi", CATEGORY_GREETING),
        ("Hello!", CATEGORY_GREETING),
        ("hey there", CATEGORY_GREETING),
        ("good morning", CATEGORY_GREETING),
        ("good evening", CATEGORY_GREETING),
        ("greetings", CATEGORY_GREETING),
        ("howdy", CATEGORY_GREETING),
        ("hello fintech", CATEGORY_GREETING),
        ("Hi there", CATEGORY_GREETING),
        ("Hey, how are you?", CATEGORY_GREETING),
        # General (10)
        ("Tell me about financial planning", CATEGORY_GENERAL),
        ("How do taxes work?", CATEGORY_GENERAL),
        ("What is wealth management?", CATEGORY_GENERAL),
        ("Explain insurance types", CATEGORY_GENERAL),
        ("What is net worth?", CATEGORY_GENERAL),
        ("Financial literacy tips", CATEGORY_GENERAL),
        ("How to achieve financial freedom?", CATEGORY_GENERAL),
        ("Money management advice", CATEGORY_GENERAL),
        ("What is an economy?", CATEGORY_GENERAL),
        ("How does inflation affect my savings?", CATEGORY_GENERAL),
    ]

    def test_at_least_100_labelled_queries(self):
        assert len(self.LABELLED_QUERIES) >= 100

    def test_accuracy_at_least_95_percent(self):
        correct = 0
        wrong = []
        for query, expected in self.LABELLED_QUERIES:
            actual = classify_query(query)
            if actual == expected:
                correct += 1
            else:
                wrong.append((query, expected, actual))
        total = len(self.LABELLED_QUERIES)
        accuracy = correct / total
        # Report failures for easier debugging
        if wrong:
            details = "\n".join(
                f"  '{q}' → expected={e}, got={a}" for q, e, a in wrong
            )
            print(f"\nMisclassified ({len(wrong)}/{total}):\n{details}")
        assert accuracy >= 0.95, (
            f"Accuracy {accuracy:.1%} is below the 95% threshold "
            f"({correct}/{total} correct)."
        )
