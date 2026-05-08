# FinTech – AI-Powered Financial Chatbot

A production-ready financial assistant chatbot that handles **100+ query types with ≥95% accuracy**, integrates real-time stock market data, and is deployable to cloud platforms like Heroku.

> Built to demonstrate **feature design, cloud readiness, automated testing, debugging, and documentation** skills.

---

## ✨ Key Features

| Feature | Detail |
|---------|--------|
| 💬 **Smart Query Classification** | Classifies queries into stock, investment, budgeting, crypto, and general categories |
| 📈 **Real-Time Stock Data** | Fetches live quotes via **yfinance** (free, no key) with **Alpha Vantage** fallback |
| 🧪 **Automated Test Suite** | 92 tests across unit + integration layers; **95.87% code coverage** |
| 📊 **Accuracy Benchmark** | 100-query labelled benchmark passes at **≥95% accuracy** |
| ☁️ **Cloud Ready** | Heroku `Procfile` + `runtime.txt` included; `gunicorn`-based production server |
| 🐛 **Bug Documentation** | `CHANGELOG.md` with root-cause analysis for 6 documented bugs |

---

## 🗂️ Project Structure

```
FinTech/
├── app.py              # Flask REST API (endpoints: /, /chat, /stock/<sym>, /health)
├── chatbot.py          # Core chatbot logic (classify, extract_ticker, get_response)
├── stock_api.py        # Real-time stock data (yfinance + Alpha Vantage)
├── requirements.txt    # Python dependencies
├── Procfile            # Heroku deployment entry point
├── runtime.txt         # Python version pinning
├── pyproject.toml      # pytest + coverage configuration
├── .env.example        # Environment variable template
├── CHANGELOG.md        # Bug fixes with root-cause analysis
└── tests/
    ├── __init__.py
    ├── test_chatbot.py  # Unit tests: classify_query, extract_ticker, get_response
    ├── test_stock_api.py# Unit tests: yfinance, Alpha Vantage, fallback logic
    └── test_app.py      # Integration tests: Flask endpoints
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- `pip`

### 1. Clone & Install

```bash
git clone https://github.com/harsha-0714/FinTech.git
cd FinTech
pip install -r requirements.txt
```

### 2. Configure Environment (optional)

```bash
cp .env.example .env
# Edit .env and set ALPHA_VANTAGE_KEY if you want the fallback API
```

The chatbot works out-of-the-box without any API keys — `yfinance` is used by default.

### 3. Run the Server

```bash
python app.py
```

Server starts at `http://localhost:5000`.

---

## 📡 API Reference

### `GET /`
Returns API metadata and endpoint listing.

```json
{
  "name": "FinTech Chatbot API",
  "version": "1.0.0",
  "endpoints": { ... }
}
```

---

### `POST /chat`
Submit a financial query and receive a structured response.

**Request:**
```json
{ "query": "What is the price of AAPL?" }
```

**Response (200):**
```json
{
  "query": "What is the price of AAPL?",
  "category": "stock",
  "response": "📈 **AAPL** — Current price: **$182.50** | Change: +1.25 (+0.69%) | Volume: 56,000,000",
  "timestamp": "2024-01-01T12:00:00Z",
  "ticker": "AAPL"
}
```

**Error (400):**
```json
{ "error": "Request body must be JSON with a 'query' field." }
```

---

### `GET /stock/<symbol>`
Get a live stock quote for a given ticker symbol.

**Example:** `GET /stock/TSLA`

**Response (200):**
```json
{
  "symbol": "TSLA",
  "price": 250.00,
  "change": -5.00,
  "change_pct": "-1.96%",
  "volume": 30000000,
  "source": "yfinance"
}
```

**Error (502):** Returned when the external stock API is unavailable.

---

### `GET /health`
Liveness probe for cloud health checks.

```json
{ "status": "ok" }
```

---

## 🧠 Query Categories

| Category | Example Queries |
|----------|----------------|
| `stock` | *"What is the price of AAPL?"*, *"TSLA stock update"*, *"Dow Jones today"* |
| `investment` | *"Best ETFs for beginners"*, *"How to diversify my portfolio?"*, *"What is a Roth IRA?"* |
| `budgeting` | *"Help me create a budget"*, *"How to pay off debt?"*, *"What is the 50/30/20 rule?"* |
| `crypto` | *"Is Bitcoin a good investment?"*, *"What are NFTs?"*, *"Ethereum vs Bitcoin"* |
| `general` | *"How do taxes work?"*, *"What is financial planning?"*, *"How does inflation affect savings?"* |
| `greeting` | *"Hello"*, *"Hi there"*, *"Good morning"* |

---

## 🧪 Running Tests

```bash
# Run all tests with coverage
python -m pytest

# Run with verbose output
python -m pytest -v

# Run a specific test file
python -m pytest tests/test_chatbot.py -v

# Generate HTML coverage report
python -m pytest --cov-report=html
# Then open htmlcov/index.html
```

### Test Results Summary

```
Name           Stmts   Miss  Cover
-----------------------------------
app.py            49      3    94%
chatbot.py       120      6    95%
stock_api.py      73      1    99%
-----------------------------------
TOTAL            242     10    96%

92 passed in 5.87s
```

### Accuracy Benchmark

The `TestAccuracyBenchmark` class validates 100 labelled queries across all categories:

```
Category      Queries    Expected Accuracy
----------    -------    -----------------
stock         20         ≥95%
investment    20         ≥95%
budgeting     20         ≥95%
crypto        20         ≥95%
greeting      10         ≥95%
general       10         ≥95%
TOTAL         100        ≥95%  ✓ (actual: 100%)
```

---

## ☁️ Deploying to Heroku

```bash
# Install Heroku CLI, then:
heroku create your-fintech-chatbot
git push heroku main

# Optional: set Alpha Vantage key
heroku config:set ALPHA_VANTAGE_KEY=your_key_here
```

The `Procfile` runs `gunicorn app:app` automatically.

---

## 🔧 Stock API Configuration

### Default: yfinance (no key required)
`yfinance` fetches data from Yahoo Finance. No API key needed.

### Fallback: Alpha Vantage (free tier)
1. Register at [alphavantage.co](https://www.alphavantage.co/support/#api-key) (free)
2. Set `ALPHA_VANTAGE_KEY=your_key` in `.env` or as an environment variable
3. The chatbot automatically uses Alpha Vantage when yfinance fails

### Supported Tickers (examples)
`AAPL`, `MSFT`, `GOOGL`, `AMZN`, `TSLA`, `META`, `NVDA`, `NFLX`, `AMD`, `JPM`, `V`, `SPY`, `QQQ`, and any valid NYSE/NASDAQ ticker.

---

## 🐛 Edge Cases & Error Handling

| Scenario | Behaviour |
|----------|-----------|
| Invalid ticker (e.g., `ZZZZZZ`) | Returns friendly error message with guidance |
| API rate limit exceeded | Retries up to 2 times, then returns error with `502` HTTP status |
| Both APIs unavailable | Returns `StockAPIError` with descriptive message |
| Empty query `""` | Returns prompt to enter a question |
| Non-string query | Flask returns `400 Bad Request` |
| Unknown query topic | Returns helpful list of supported topics |
| `None` as query | Safely handled, returns `unknown` category |

---

## 📋 Test Plan

### Unit Tests (`test_chatbot.py`)
- **Classify query** – all 7 categories, edge cases (empty, None, numeric input)
- **Extract ticker** – known tickers, price-of pattern, stock-suffix pattern, no-ticker case
- **Get response** – all categories, API error handling, timestamp presence, query stripping
- **Accuracy benchmark** – 100 labelled queries, ≥95% pass rate

### Unit Tests (`test_stock_api.py`)
- **Input validation** – empty string, whitespace, None, symbol uppercasing
- **yfinance path** – success, change calculation, None price, exceptions, volume defaults
- **Alpha Vantage path** – success, missing key, empty response, HTTP errors, type casting
- **Fallback logic** – yfinance fail → Alpha Vantage, both fail, yfinance used first
- **Batch quotes** – all success, partial failure, empty list, invalid symbol

### Integration Tests (`test_app.py`)
- **Root endpoint** – 200 status, JSON schema
- **Health endpoint** – 200 status, `ok` response
- **Chat endpoint** – missing body/key (400), non-string (400), all categories (200)
- **Stock endpoint** – success (200), API error (502), ValueError (400), symbol uppercasing
- **Error handlers** – 404, 405 return JSON

---

## 📦 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.3 | Web framework |
| yfinance | 0.2.40 | Free stock data (primary) |
| requests | 2.32.3 | Alpha Vantage HTTP calls |
| gunicorn | 22.0.0 | Production WSGI server |
| python-dotenv | 1.0.1 | `.env` file loading |
| pytest | 8.2.2 | Test runner |
| pytest-cov | 5.0.0 | Coverage reporting |

---

## 📄 License

MIT
