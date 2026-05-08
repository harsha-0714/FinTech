# Changelog

All notable changes to the FinTech chatbot project are documented here.  
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.0.0] – 2024-01-01

### Added
- Core chatbot logic (`chatbot.py`) with query classification and response generation.
- Real-time stock data integration (`stock_api.py`) using **yfinance** (primary) and  
  **Alpha Vantage** (fallback).
- Flask REST API (`app.py`) with `/chat`, `/stock/<symbol>`, and `/health` endpoints.
- Automated test suite (`tests/`) with **92 tests** and **95.87% code coverage**.
- Accuracy benchmark: classifies **100+ queries with ≥95% accuracy**.
- Heroku deployment configuration (`Procfile`, `runtime.txt`).
- Environment variable documentation (`.env.example`).

---

## Bug Fixes & Root-Cause Analysis

### BUG-001 – Regex word-boundary caused classification misses for plural/conjugated words

| Field         | Detail |
|---------------|--------|
| **Symptom**   | `classify_query("Best ETFs for beginners")` returned `unknown` instead of `investment`. |
| **Root Cause**| Investment pattern used a trailing `\b` after `etf`, so `etfs` (plural) fell outside the boundary and was not matched. Same issue affected `stocks`, `expenses`, `altcoins`, and `ipos`. |
| **Fix**       | Rewrote all keyword patterns to use `\b(?:keyword…)` without a trailing `\b`. Plural/conjugated forms like `etfs?`, `altcoins?`, `stocks?` are now captured. |
| **Tests**     | `test_investment_etf`, `test_budgeting_expense`, `test_stock_keyword`, `test_ipo_classified_as_stock`, `TestAccuracyBenchmark::test_accuracy_at_least_95_percent` |
| **Coverage Δ**| Overall accuracy rose from 74% to ≥95% on the 100-query benchmark. |

---

### BUG-002 – General financial category never triggered

| Field         | Detail |
|---------------|--------|
| **Symptom**   | Queries like `"Tell me about financial planning"` and `"How do taxes work?"` returned `unknown` instead of `general`. |
| **Root Cause**| The general-category regex `\b(financ|money|wealth|econom|tax|insurance)\b` required a word boundary after the stem, so `"financial"` (continuing after `financ`) and `"taxes"` (suffix `es`) did not match. |
| **Fix**       | Changed to `\b(?:financ|money|wealth|econom|tax|insurance|literac|freedom|inflation)` (no trailing `\b`), matching all inflected forms. Added `literac`, `freedom`, `inflation` to expand coverage. |
| **Tests**     | `test_general_finance`, `test_general_tax`, `TestGetResponse::test_general_response` |

---

### BUG-003 – `datetime.utcnow()` deprecation in Python 3.12+

| Field         | Detail |
|---------------|--------|
| **Symptom**   | `DeprecationWarning: datetime.datetime.utcnow() is deprecated` in test output. |
| **Root Cause**| Python 3.12 deprecated `datetime.utcnow()` in favour of timezone-aware datetime objects. |
| **Fix**       | Replaced all `datetime.utcnow()` calls with `datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")`. |
| **Tests**     | `test_response_has_timestamp` verifies the timestamp ends with `Z`. |

---

### BUG-004 – Alpha Vantage request never retried on transient HTTP errors

| Field         | Detail |
|---------------|--------|
| **Symptom**   | A single 503 Service Unavailable response from Alpha Vantage immediately raised `StockAPIError`, with no retry. |
| **Root Cause**| The retry loop called `raise_for_status()` inside the loop but the exception was not caught in the retry branch; it escaped directly. |
| **Fix**       | Wrapped `raise_for_status()` and JSON parsing in a `try/except (requests.RequestException, ValueError, KeyError)` block that sleeps 1 second before retrying. `retries=2` by default. |
| **Tests**     | `TestAlphaVantagePath::test_http_error_retries_and_raises` |

---

### BUG-005 – Fallback to Alpha Vantage silently ignored when `yfinance` fails

| Field         | Detail |
|---------------|--------|
| **Symptom**   | When `yfinance` raised `StockAPIError`, the error propagated directly instead of trying Alpha Vantage. |
| **Root Cause**| `get_stock_quote()` caught all exceptions from `_fetch_yfinance`, but the check `if _alpha_vantage_key():` was missing, so the fallback path was never entered. |
| **Fix**       | Added explicit `StockAPIError` catch around the yfinance call, logged the failure, then proceeded to the Alpha Vantage fallback if `_alpha_vantage_key()` is set. |
| **Tests**     | `TestFallbackLogic::test_falls_back_to_alpha_vantage_when_yfinance_fails` |

---

### BUG-006 – `/stock/<symbol>` endpoint returned 500 instead of 502 for API errors

| Field         | Detail |
|---------------|--------|
| **Symptom**   | When the stock back-end was unavailable, the Flask endpoint returned an unhandled 500. |
| **Root Cause**| `StockAPIError` was not explicitly caught in the route handler; only `ValueError` was handled. |
| **Fix**       | Added a dedicated `except StockAPIError` branch in `/stock/<symbol>` that returns HTTP 502 Bad Gateway with a structured JSON error body. |
| **Tests**     | `TestStockEndpoint::test_api_error_returns_502` |
