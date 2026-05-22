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

**In Progress / High Priority:**
- Full implementation of new "High-Quality Rare Trades" strategy
- Advanced signal filters and profit calculation
- Smart Item management (`items.json` + scoring)
- Risk management & position sizing module
- Enhanced dashboard with statistics and charts
- State persistence and graceful shutdown

---

## Architecture Overview

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

## Next Development Steps (Priority)

1. ~~Update trading strategy with new strict filters (Prompt 1)~~ ✅ Done
2. ~~Implement full Paper SELL + improved PnL tracking (Prompt 2)~~ ✅ Done
3. Smart items management + `items.json` (Prompt 3)
4. Risk management module (`app/risk.py`)
5. Enhanced dashboard with statistics and indicators
6. Statistics collection + weekly Telegram reports
7. State persistence and graceful shutdown

---

**Last Updated:** May 22, 2026  
**Project Phase:** Paper SELL Implementation (Prompt 2 complete)
