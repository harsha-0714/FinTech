"""
chatbot.py – Core chatbot logic for the FinTech financial assistant.

Responsibilities
----------------
* Classify incoming user queries (stock lookup, investment, budgeting, general).
* Generate appropriate text responses.
* Delegate real-time stock lookups to stock_api.get_stock_quote().
* Maintain per-session query history (optional).

Design goals
------------
* All public functions are pure / side-effect-free where possible so that
  they are easy to unit-test without mocking I/O.
* Stock API calls are isolated behind get_stock_quote(), making them simple
  to mock in tests.
"""

from __future__ import annotations

import re
import logging
from typing import Optional
from datetime import datetime, timezone

from stock_api import get_stock_quote, StockAPIError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Query categories
# ---------------------------------------------------------------------------
CATEGORY_STOCK = "stock"
CATEGORY_INVESTMENT = "investment"
CATEGORY_BUDGETING = "budgeting"
CATEGORY_CRYPTO = "crypto"
CATEGORY_GENERAL = "general"
CATEGORY_GREETING = "greeting"
CATEGORY_UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# Keyword patterns used for classification
# ---------------------------------------------------------------------------
_GREETING_WORDS = frozenset(
    ["hi", "hello", "hey", "howdy", "greetings", "good morning",
     "good afternoon", "good evening"]
)

_STOCK_PATTERNS = re.compile(
    r"\b(?:stocks?|shares?|price|ticker|equity|market\s+cap|dividend|"
    r"nasdaq|nyse|s&p|sp500|dow\s+jones|ipos?)",
    re.IGNORECASE,
)

_TICKER_PATTERN = re.compile(r"\b([A-Z]{1,5})\b")  # potential ticker symbol

_INVESTMENT_PATTERNS = re.compile(
    r"\b(?:invest|portfolio|returns?|yield|mutual\s+fund|etfs?|bonds?|"
    r"diversif|risk|asset\s+alloc|rebalanc|index\s+fund|roth|401k|ira|"
    r"compound\s+interest|dollar.cost|real\s+estate)",
    re.IGNORECASE,
)

_BUDGETING_PATTERNS = re.compile(
    r"\b(?:budget|expenses?|savings?|sav(?:e|ing)|spend|debt|loan|"
    r"mortgage|emergency\s+fund|net\s+worth|cash\s+flow|income|"
    r"salary|bills?|credit\s+score|zero.based|50/30/20)",
    re.IGNORECASE,
)

_CRYPTO_PATTERNS = re.compile(
    r"\b(?:crypto|bitcoin|btc|ethereum|eth|altcoins?|defi|nfts?|blockchain|"
    r"litecoin|ripple|xrp|dogecoin|doge|halving|web3)",
    re.IGNORECASE,
)

# Common well-known tickers used to identify explicit stock queries
_KNOWN_TICKERS = frozenset([
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA",
    "NFLX", "UBER", "LYFT", "AMD", "INTC", "IBM", "ORCL", "CRM",
    "JPM", "GS", "BAC", "WFC", "V", "MA", "PYPL",
    "SPY", "QQQ", "DIA",
])


# ---------------------------------------------------------------------------
# Static response banks
# ---------------------------------------------------------------------------

_INVESTMENT_TIPS = [
    "Diversify your portfolio across asset classes to reduce risk.",
    "Low-cost index funds (e.g., S&P 500 ETFs) outperform most active funds over 10+ years.",
    "Follow the 3-fund portfolio strategy: domestic stocks, international stocks, and bonds.",
    "Max out your tax-advantaged accounts (401k, IRA/Roth IRA) before taxable investing.",
    "Rebalance your portfolio annually to maintain your target allocation.",
    "Avoid trying to time the market; time *in* the market beats timing the market.",
    "Keep an emergency fund (3–6 months of expenses) before investing.",
    "Dollar-cost averaging reduces the impact of market volatility on large purchases.",
]

_BUDGETING_TIPS = [
    "The 50/30/20 rule: 50% needs, 30% wants, 20% savings/debt repayment.",
    "Track every expense for one month to identify unnecessary spending.",
    "Automate savings transfers on payday to pay yourself first.",
    "High-interest debt (credit cards) should be paid off before investing.",
    "Build an emergency fund covering 3–6 months of essential living costs.",
    "Review and cancel unused subscriptions each quarter.",
    "Use zero-based budgeting to allocate every rupee/dollar of income purposefully.",
]

_CRYPTO_TIPS = [
    "Crypto is highly volatile—never invest more than you can afford to lose.",
    "Bitcoin (BTC) and Ethereum (ETH) are the most established cryptocurrencies.",
    "Store large crypto holdings in a hardware wallet, not on an exchange.",
    "Understand the tax implications of crypto trading in your jurisdiction.",
    "DeFi protocols can offer high yields but carry smart-contract risk.",
]

_GENERAL_TIPS = [
    "Start investing early—compound interest is the eighth wonder of the world.",
    "Financial literacy is a lifelong skill; read at least one finance book per year.",
    "Net worth = assets − liabilities. Track yours quarterly.",
    "Insurance (health, life, disability) is a crucial part of a financial plan.",
    "Consult a certified financial planner (CFP) for personalised advice.",
]


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_query(query: str) -> str:
    """
    Return a category string for the given *query*.

    Categories (in priority order):
        greeting, stock, crypto, investment, budgeting, general, unknown
    """
    if not isinstance(query, str):
        return CATEGORY_UNKNOWN
    q = query.strip()
    if not q:
        return CATEGORY_UNKNOWN

    q_lower = q.lower()

    # Greeting
    if any(q_lower.startswith(word) for word in _GREETING_WORDS) or q_lower in _GREETING_WORDS:
        return CATEGORY_GREETING

    # Stock – explicit ticker or stock-related keywords
    if _STOCK_PATTERNS.search(q):
        return CATEGORY_STOCK
    # Check if any KNOWN ticker appears
    words = {w.upper() for w in re.findall(r"\b[A-Za-z]{1,5}\b", q)}
    if words & _KNOWN_TICKERS:
        return CATEGORY_STOCK

    # Crypto
    if _CRYPTO_PATTERNS.search(q):
        return CATEGORY_CRYPTO

    # Investment
    if _INVESTMENT_PATTERNS.search(q):
        return CATEGORY_INVESTMENT

    # Budgeting
    if _BUDGETING_PATTERNS.search(q):
        return CATEGORY_BUDGETING

    # General financial
    if re.search(r"\b(?:financ|money|wealth|econom|tax|insurance|literac|freedom|inflation)", q, re.IGNORECASE):
        return CATEGORY_GENERAL

    return CATEGORY_UNKNOWN


# ---------------------------------------------------------------------------
# Ticker extraction
# ---------------------------------------------------------------------------

def extract_ticker(query: str) -> Optional[str]:
    """
    Attempt to extract a stock ticker symbol from *query*.

    Returns the first known ticker found, or the first all-caps word of 1-5
    letters that looks like a ticker, or None.
    """
    words = {w.upper() for w in re.findall(r"\b[A-Za-z]{1,5}\b", query)}
    # Prefer known tickers
    known = words & _KNOWN_TICKERS
    if known:
        return sorted(known)[0]

    # Heuristic: find explicit uppercase token like "TSLA" or "price of NVDA"
    match = re.search(r"\bprice\s+of\s+([A-Z]{1,5})\b", query, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    match = re.search(r"\b([A-Z]{2,5})\s+stock\b", query, re.IGNORECASE)
    if match:
        candidate = match.group(1).upper()
        # Filter out common English words
        _STOP_WORDS = {"THE", "FOR", "AND", "BUY", "SELL", "GET", "TOP",
                       "CAN", "ARE", "HOW", "WHY", "WHAT", "WHEN", "WHO"}
        if candidate not in _STOP_WORDS:
            return candidate

    return None


# ---------------------------------------------------------------------------
# Response generators
# ---------------------------------------------------------------------------

def _stock_response(query: str) -> str:
    ticker = extract_ticker(query)
    if ticker:
        try:
            quote = get_stock_quote(ticker)
            change_sign = "+" if quote["change"] >= 0 else ""
            return (
                f"📈 **{quote['symbol']}** — "
                f"Current price: **${quote['price']:.2f}** | "
                f"Change: {change_sign}{quote['change']:.2f} "
                f"({change_sign}{quote['change_pct']}) | "
                f"Volume: {quote['volume']:,} | "
                f"Source: {quote['source']}"
            )
        except StockAPIError as exc:
            logger.error("Stock API error for %s: %s", ticker, exc)
            return (
                f"⚠️ Could not retrieve live data for **{ticker}** right now. "
                f"Reason: {exc}. "
                "Please try again later or check the ticker symbol."
            )
    return (
        "📊 To get a live stock quote, mention the ticker symbol in your query. "
        "For example: *'What is the price of AAPL?'* or *'Show me TSLA stock'*."
    )


def _investment_response() -> str:
    import random
    tips = random.sample(_INVESTMENT_TIPS, min(3, len(_INVESTMENT_TIPS)))
    lines = "\n".join(f"  • {t}" for t in tips)
    return (
        "💰 **Investment Guidance**\n"
        f"{lines}\n\n"
        "*Remember: Past performance does not guarantee future results. "
        "Consider consulting a financial advisor for personalised advice.*"
    )


def _budgeting_response() -> str:
    import random
    tips = random.sample(_BUDGETING_TIPS, min(3, len(_BUDGETING_TIPS)))
    lines = "\n".join(f"  • {t}" for t in tips)
    return (
        "🗂️ **Budgeting Tips**\n"
        f"{lines}\n\n"
        "*Small, consistent changes to spending habits compound into large "
        "savings over time.*"
    )


def _crypto_response() -> str:
    import random
    tips = random.sample(_CRYPTO_TIPS, min(3, len(_CRYPTO_TIPS)))
    lines = "\n".join(f"  • {t}" for t in tips)
    return (
        "₿ **Cryptocurrency Guidance**\n"
        f"{lines}\n\n"
        "*Cryptocurrency markets operate 24/7 and are highly speculative.*"
    )


def _general_response() -> str:
    import random
    tips = random.sample(_GENERAL_TIPS, min(2, len(_GENERAL_TIPS)))
    lines = "\n".join(f"  • {t}" for t in tips)
    return (
        "🏦 **General Financial Advice**\n"
        f"{lines}\n\n"
        "Ask me about stocks, investments, budgeting, or cryptocurrency "
        "for more specific guidance."
    )


def _greeting_response() -> str:
    return (
        "👋 Hello! I'm your FinTech financial assistant.\n\n"
        "I can help you with:\n"
        "  📈 **Stock prices** – e.g., *'What is the price of AAPL?'*\n"
        "  💰 **Investment advice** – e.g., *'How should I invest $10,000?'*\n"
        "  🗂️ **Budgeting tips** – e.g., *'Help me create a budget'*\n"
        "  ₿ **Crypto guidance** – e.g., *'Tell me about Bitcoin'*\n\n"
        "What would you like to know?"
    )


def _unknown_response() -> str:
    return (
        "🤔 I'm not sure I understood that. I specialise in financial topics.\n\n"
        "Try asking about:\n"
        "  • Stock prices (e.g., *'TSLA stock price'*)\n"
        "  • Investment strategies (e.g., *'best ETFs for beginners'*)\n"
        "  • Budgeting advice (e.g., *'how to save money'*)\n"
        "  • Cryptocurrency (e.g., *'is Bitcoin a good investment?'*)"
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def get_response(query: str) -> dict:
    """
    Process a user *query* and return a response dict.

    Returns
    -------
    dict with keys:
        query      : str  – original query (stripped)
        category   : str  – detected category
        response   : str  – chatbot response text
        timestamp  : str  – ISO-8601 UTC timestamp
        ticker     : str | None – extracted ticker (stock queries only)
    """
    query = (query or "").strip()
    if not query:
        return {
            "query": "",
            "category": CATEGORY_UNKNOWN,
            "response": "Please enter a question or query.",
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "ticker": None,
        }

    category = classify_query(query)
    ticker: Optional[str] = None

    if category == CATEGORY_GREETING:
        response_text = _greeting_response()
    elif category == CATEGORY_STOCK:
        ticker = extract_ticker(query)
        response_text = _stock_response(query)
    elif category == CATEGORY_INVESTMENT:
        response_text = _investment_response()
    elif category == CATEGORY_BUDGETING:
        response_text = _budgeting_response()
    elif category == CATEGORY_CRYPTO:
        response_text = _crypto_response()
    elif category == CATEGORY_GENERAL:
        response_text = _general_response()
    else:
        response_text = _unknown_response()

    logger.info("query=%r category=%s ticker=%s", query, category, ticker)

    return {
        "query": query,
        "category": category,
        "response": response_text,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "ticker": ticker,
    }
