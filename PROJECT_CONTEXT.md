# Steam Monitor — Project Context

## Project Goal & Vision

**Main Objective:**
Build a reliable semi-automated trading tool for the Steam Market that helps generate **3,000 – 7,000 RUB per month** for buying games and in-game items.

**Target Capital:** 20,000 – 50,000 RUB  
**Target Monthly Return:** 8–18% net (after Steam 15% fee)  
**Trading Style:** Low-frequency, high-quality trades (8–20 trades per month)

**Core Approach:** 
- Semi-automated system: bot detects high-quality opportunities → sends clear signal with reasoning → user makes final decision manually (to minimize Steam ban risk).
- Focus on sustainable small-profit trading rather than aggressive scalping.

---

## Trading Strategy Overview

**Current Strategy (Updated May 2026):** "High-Quality Mean Reversion"

### Core Principles:
- Rare but high-probability setups instead of noisy frequent signals
- Strong focus on oversold conditions with confirmed liquidity
- Always calculate expected profit **after Steam 15% commission**
- Risk management and position sizing are mandatory

### BUY Signal Requirements (Strict):
1. RSI(14) ≤ 35 (strong oversold)
2. Current price below Lower Bollinger Band
3. Deviation from EMA20 ≥ 22%
4. Daily volume ≥ 80 sales (good liquidity)
5. Estimated net profit after 15% fee ≥ 15% (projected exit near EMA20 or Middle BB)
6. Item price in range 30 – 2500 RUB

### SELL Signal Requirements:
- RSI(14) ≥ 68 OR
- Price touches Upper Bollinger Band OR
- Realized profit from entry ≥ 14% OR
- Trailing stop logic (optional)

**Performance Targets:**
- Win Rate ≥ 65%
- Average Net Profit per Trade ≥ 9–11%
- Average hold time: 2–12 days

---

## Current Status (as of May 22, 2026)

**Completed:**
- Core project architecture and folder structure
- SQLite database with SQLAlchemy
- Steam Market Price Overview API client (`steam_api.py`)
- Technical indicators (RSI, EMA20, Bollinger Bands)
- Basic monitoring loop (`monitor.py`)
- Paper Trading (BUY + SELL + full PnL tracking)
- Telegram notifications with chart images
- Streamlit dashboard (`web/dashboard.py`)
- Basic logging and configuration system
- ✅ Steam API 429 rate limit handling with exponential backoff
- ✅ RUB currency price parsing (handles '135,00 ₽' and '1 350,00 ₽' formats)
- ✅ median_price as primary source, lowest_price as fallback (most items have only median)

**In Progress / High Priority:**
- Full implementation of new "High-Quality Rare Trades" strategy
- Advanced signal filters and profit calculation
- Smart Item management (`items.json` + scoring)
- Risk management & position sizing module
- Enhanced dashboard with statistics and charts
- State persistence and graceful shutdown

---

## Architecture Overview

### Docker

Two services: **dashboard** (bridge network, port 8501) + **monitor** (host network, bypasses Steam IP blocks).

- `dashboard`: Streamlit UI, published on `8501:8501`, shared volumes for `data/`, `logs/`, `charts/`.
- `monitor`: `network_mode: host`, runs `python main.py` for Steam API polling using the host network stack.

**Main Components:**
- `main.py` → Entry point (starts dashboard and/or monitor)
- `app/` → Core business logic
- `web/` → Streamlit dashboard
- `data/` → Database, items, logs, charts
- `charts/` → Generated visualization images

**Key Modules:**
- `config.py` — All settings, thresholds, API keys
- `trading_engine.py` — Main signal analysis logic
- `signals.py` — Signal evaluation and Telegram triggering
- `monitor.py` — Main scanning loop for items
- `indicators.py` — Technical analysis calculations
- `paper_trading.py` — Virtual trading simulation
- `wallet.py` — Virtual wallet balance management
- `notifier.py` — Telegram alerts and chart sending
- `models.py` — SQLAlchemy database models
- `database.py` — DB session management
- `roi.py` — Profit, fee, and ROI calculations

---

## External APIs

| API              | Endpoint                                      | Purpose                              |
|------------------|-----------------------------------------------|--------------------------------------|
| Steam Market     | `https://steamcommunity.com/market/priceoverview/` | Price, volume, median price data |
| Telegram Bot     | `https://api.telegram.org`                    | Notifications + chart images         |

---

## Non-Functional Requirements

- Maximum safety — **no automatic real money trading**
- Minimize risk of Steam ban (rare requests + random delays)
- Resilience to restarts (persist latest indicator values)
- Clean, informative, visually appealing dashboard
- Comprehensive logging with different levels
- Easy extensibility for new strategies and items

---

## Folder Structure

steam-monitor/
├── main.py                          # Entry point
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── PROJECT_CONTEXT.md
├── commands.txt
│
├── data/
│   ├── steam_cards.db               # SQLite database
│   ├── items.json                   # List of tracked items
│   └── logs/
│
├── app/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── logger.py
│   ├── steam_api.py
│   ├── monitor.py
│   ├── indicators.py
│   ├── trading_engine.py
│   ├── signals.py
│   ├── paper_trading.py
│   ├── wallet.py
│   ├── notifier.py
│   ├── roi.py
│   └── alert_store.py
│
├── web/
│   └── dashboard.py                 # Streamlit UI
│
├── charts/                          # Generated chart images
└── logs/
text


---

## Known Issues / Bugs

### Fixed Issues:
- ✅ **FIXED: Docker container SSL timeout on steamcommunity.com**
- **Root cause:** Steam blocks virtual/NAT IPs from Docker
- **Solution:** monitor service uses `network_mode: host`

## Known Issues / Fixes (May 2026)

### Fixed Issues:
- ✅ **Steam API 429 Rate Limiting** — Added exponential backoff handling (wait 60s × attempt number)
- ✅ **Steam returns None for prices** — Implemented robust RUB price parsing for formats like '135,00 ₽' and '1 350,00 ₽'
- ✅ **Price parsing** — Handles mixed thousand separators and currency symbols; distinguishes decimal separator intelligently
- ✅ **Most items return only median_price** — Switched to median_price as primary, lowest_price as fallback (real API behavior)

### Configuration Notes:
- **STEAM_REQUEST_DELAY_MIN/MAX:** Set to 10–20 seconds to avoid Steam 429 bans
- **429 Handling:** Bot will wait exponentially (60s, 120s, 180s) and retry on rate limit
- **Price Source:** Steam API returns median_price for most items, lowest_price rarely. Logic now prioritizes median_price.

---

## Known Limitations

- `network_mode: host` only works on Linux Docker. On Windows/Mac Docker Desktop: use `host.docker.internal` OR run `python main.py` directly on the Windows host.

---

## Configuration (.env)

**Steam API:**
- `STEAM_REQUEST_DELAY_MIN=10` — Minimum delay between Steam requests (seconds)
- `STEAM_REQUEST_DELAY_MAX=20` — Maximum delay between Steam requests (seconds)
- *Keep 10–20s delays to avoid Steam 429 rate limit bans*

---

## Next Development Steps (Priority)

1. ~~Update trading strategy with new strict filters (Prompt 1)~~ ✅ Done
2. ~~Implement full Paper SELL + improved PnL tracking (Prompt 2)~~ ✅ Done
3. ~~Smart items management + `items.json` (Prompt 3)~~ ✅ Done
4. ✅ Steam API price parsing for RUB currency
5. ✅ Steam 429 rate limit handling with backoff
6. Risk management module (`app/risk.py`)
7. Enhanced dashboard with statistics and indicators
8. Statistics collection + weekly Telegram reports
9. State persistence and graceful shutdown
10. ✅ Docker network fix for Steam API access
11. ✅ Steam API headers updated

---

**Last Updated:** May 25, 2026  
**Project Phase:** Docker network fixed, Steam API headers corrected
