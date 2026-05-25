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
- ✅ Risk management & position sizing module (`app/risk_manager.py`)
- Enhanced dashboard with statistics and charts
- State persistence and graceful shutdown

---

## Architecture Overview

### Docker

Single service, full Docker deployment.

- `steam-monitor`: builds from `Dockerfile`, runs `main.py` (dashboard + monitor), published on `8501:8501`, shared volumes for `data/`, `logs/`, `charts/`.
- Steam IP blocks solved via session cookie authentication (`STEAM_SESSION_COOKIE`, `STEAM_LOGIN_SECURE` in `.env`).

**Main Components:**
- `main.py` → Entry point (starts dashboard and/or monitor)
- `app/` → Core business logic
- `web/` → Streamlit dashboard
- `data/` → Database, items, logs, charts
- `charts/` → Generated visualization images

**Key Modules:**
- `config.py` — All settings, thresholds, API keys
- `scanner.py` — Auto-discovers liquid CS2 items from Steam Market search; updates `items.json` safely with popularity/volume filtering; respects Steam anti-rate-limit delays
- `trading_engine.py` — Main signal analysis logic
- `signals.py` — Signal evaluation and Telegram triggering
- `monitor.py` — Main scanning loop for items
- `indicators.py` — Technical analysis calculations
- `paper_trading.py` — Virtual trading simulation
- `wallet.py` — Virtual wallet balance management
- `notifier.py` — Telegram alerts and chart sending (network-fault tolerant; optional SOCKS5/HTTP proxy)
- `models.py` — SQLAlchemy database models
- `database.py` — DB session management
- `roi.py` — Profit, fee, and ROI calculations
- `history.py` — Dedicated SQLite price snapshot store (`data/price_history.db`) for analytics and trend detection
- `analytics.py` — Read-only profitability scoring engine (`MarketAnalytics`) over price history DB; no Steam/network calls
- `risk_manager.py` — Position sizing, portfolio heat limits, and trade approval gates (`RiskManager`)
- `backtester.py` — Historical walk-forward simulation with risk-managed sizing

---

## Risk Management System

`RiskManager` (`app/risk_manager.py`) enforces capital preservation rules before paper BUY execution and during backtests.

**Position sizing (`calculate_position_size`):**
- Base budget per trade: `account_balance × MAX_RISK_PER_TRADE` (default **1.5%**)
- **Higher `profit_score`** → larger multiplier (0.5×–1.0× on the risk budget)
- **Higher volatility risk** (price CV mapped 0–100) → smaller multiplier (down to 0.25×)
- Optional global scale via `POSITION_SCALING_FACTOR`
- Returns **0** when balance invalid or size below minimum (1 ₽)

**Portfolio heat (`check_portfolio_heat`):**
- Sum of open position `cost` values divided by balance must stay ≤ `MAX_PORTFOLIO_HEAT` (default **30%**)
- `is_trade_allowed` also rejects a new BUY if it would push heat over the limit

**Trade gate (`is_trade_allowed`):**
- Requires `profit_score ≥ MIN_PROFIT_SCORE_ALERT` when a score is available (≥ 0)
- Validates balance, heat headroom, and non-zero position size
- Returns `(bool, reason)` — never raises on missing data

**Dynamic stop loss (`calculate_dynamic_stop_loss`):**
- Stop price below entry; distance scales with volatility (base ~8%, up to ~25%)

**Integration:**
- `monitor.py` — risk pre-check logging before `evaluate_and_notify`
- `signals.py` — blocks BUY → `HOLD` when risk fails; sizes paper quantity from `calculate_position_size`
- `backtester.py` — applies the same gates and stop-loss exits during simulation

| Setting | Default | Purpose |
|---------|---------|---------|
| `MAX_RISK_PER_TRADE` | `0.015` | Max fraction of balance risked per new position |
| `MAX_PORTFOLIO_HEAT` | `0.30` | Max fraction of balance in open positions |
| `POSITION_SCALING_FACTOR` | `1.0` | Global multiplier on computed position size |

---

## Price History Database (Analytics)

Separate from the main SQLAlchemy DB (`data/steam_cards.db`), the monitor writes time-series snapshots to **`data/price_history.db`** after each successful Steam price fetch.

| Setting | Default | Purpose |
|---------|---------|---------|
| `PRICE_HISTORY_DB` | `data/price_history.db` | SQLite file path (persisted via Docker `./data` volume) |
| `PRICE_HISTORY_RETENTION_DAYS` | `30` | Auto-delete snapshots older than N days |

**Schema (`price_history` table):**
- `id`, `item_name`, `price`, `volume`, `timestamp`
- Index on `(item_name, timestamp)`
- WAL mode, retry on `database locked`, background writer thread (non-blocking monitor loop)

**Retention:** Cleanup runs automatically (~hourly) in the history worker; failures are logged and never stop the monitor.

**Intelligent market scoring (`app/analytics.py`):**
- `MarketAnalytics` reads `price_history.db` in read-only mode (WAL-safe, short timeout, indexed queries)
- Runs after each monitor cycle when at least one price was saved; failures never stop the monitor
- Per-item metrics: price change, liquidity, volatility (moderate preferred), momentum, spread stability
- `profit_score` (0–100) combines movement, liquidity, volatility, and spread stability; low-history items skipped
- `get_top_opportunities()` logs ranked items; optional Telegram alerts when `profit_score >= MIN_PROFIT_SCORE_ALERT` (cooldown via `alert_store`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `MIN_HISTORY_SNAPSHOTS` | `20` | Minimum snapshots in lookback window to score an item |
| `ANALYTICS_LOOKBACK_HOURS` | `24` | History window for all analytics queries |
| `MIN_PROFIT_SCORE_ALERT` | `70` | Telegram alert threshold for high profit scores |

**Historical analytics roadmap:**
- [x] Profitability scoring per item from historical price and volume
- [ ] Trend detection (moving averages, drawdowns, seasonality)
- [ ] Cross-item correlation and scanner quality feedback
- [ ] Dashboard charts sourced from dedicated history DB
- [ ] Smarter alert deduplication and weekly analytics digest

---

## External APIs

| API              | Endpoint                                      | Purpose                              |
|------------------|-----------------------------------------------|--------------------------------------|
| Steam Market     | `https://steamcommunity.com/market/priceoverview/` | Price, volume, median price data |
| Steam Market     | `https://steamcommunity.com/market/search/render/` | Auto-scanner: discover popular CS2 listings |
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
│   ├── steam_cards.db               # Main SQLite (signals, paper trading)
│   ├── price_history.db             # Analytics price snapshots (WAL)
│   ├── items.json                   # List of tracked items
│   └── logs/
│
├── app/
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── logger.py
│   ├── steam_api.py
│   ├── scanner.py
│   ├── monitor.py
│   ├── indicators.py
│   ├── trading_engine.py
│   ├── signals.py
│   ├── paper_trading.py
│   ├── wallet.py
│   ├── notifier.py
│   ├── roi.py
│   ├── history.py
│   ├── analytics.py
│   ├── risk_manager.py
│   ├── backtester.py
│   └── alert_store.py
│
├── web/
│   └── dashboard.py                 # Streamlit UI
│
├── charts/                          # Generated chart images
└── logs/
text


---

## Notifications

- Telegram notifications are **network-fault tolerant**: configurable timeout, retries with delay, and clear failure logging without blocking the monitor loop
- Optional **SOCKS5/HTTP proxy** via `TELEGRAM_PROXY_URL` when Telegram is blocked or unstable in the host region

---

## Security Notes

- **NEVER commit `.env`**
- `.env` contains Telegram bot credentials and Steam session tokens
- Proxy credentials may also exist in `.env`
- Steam cookies expire ~30 days — refresh when 429s or blocks increase
- Auto-scanner uses authenticated Steam session cookies (`STEAM_SESSION_COOKIE`, `STEAM_LOGIN_SECURE`) — never log cookie values

---

## Known Issues / Bugs

### Fixed Issues:
- ✅ **FIXED: Steam Docker IP block** — Authenticated requests via `sessionid` + `steamLoginSecure` cookies in `.env`
- ✅ **FIXED: Docker container SSL timeout on steamcommunity.com** (superseded by cookie auth; no `network_mode: host` required)

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

### Telegram / connectivity:
- Telegram may be blocked in some regions
- Use `TELEGRAM_PROXY_URL` if requests timeout
- High retry delays can slow notifications

### Steam Market scanner:
- Steam Market scanning may trigger rate limits (HTTP 429)
- Aggressive scan intervals (`AUTO_SCAN_INTERVAL_HOURS` too low) increase block risk
- Scanner depends on Steam Market search API availability
- Use `SCANNER_REQUEST_DELAY` ≥ 5s and keep `SCAN_TOTAL_ITEMS` modest (default 50)

---

## Configuration (.env)

**Telegram:**
- `TELEGRAM_REQUEST_TIMEOUT` — HTTP timeout per Telegram API request (seconds, default 15)
- `TELEGRAM_PROXY_URL` — Optional SOCKS5/HTTP proxy URL (empty = direct connection)
- `TELEGRAM_MAX_RETRIES` — Retry count on network errors (default 3)
- `TELEGRAM_RETRY_DELAY` — Seconds between retry attempts (default 3)

**Steam session (required for Docker):**
- `STEAM_SESSION_COOKIE` — `sessionid` cookie from steamcommunity.com (browser DevTools → Application → Cookies)
- `STEAM_LOGIN_SECURE` — `steamLoginSecure` cookie from the same place
- Refresh both ~every 30 days when 429s or blocks increase

**Steam API:**
- `STEAM_REQUEST_DELAY_MIN=10` — Minimum delay between Steam requests (seconds)
- `STEAM_REQUEST_DELAY_MAX=20` — Maximum delay between Steam requests (seconds)
- *Keep 10–20s delays to avoid Steam 429 rate limit bans*

**Auto scanner:**
- `AUTO_SCAN_ENABLED` — Run market discovery on monitor startup (`false` by default)
- `AUTO_SCAN_INTERVAL_HOURS` — Minimum hours between scans (default 24)
- `SCAN_TOTAL_ITEMS` — Max new listings to fetch per scan (default 50)
- `SCANNER_REQUEST_DELAY` — Seconds between scanner HTTP requests (default 5)
- `MIN_PRICE_RUB` / `MAX_PRICE_RUB` — Scanner price filter range (defaults 50–5000)
- `MIN_VOLUME_PER_DAY` — Minimum listing volume for scanner (default 20; raise in `.env` for stricter trading signals, e.g. 80)

**Price history (analytics DB):**
- `PRICE_HISTORY_DB` — Path to dedicated snapshot SQLite (default `data/price_history.db`)
- `PRICE_HISTORY_RETENTION_DAYS` — Days to keep snapshots before auto-cleanup (default 30)
- `MIN_HISTORY_SNAPSHOTS` — Minimum snapshots required to score an item (default 20)
- `ANALYTICS_LOOKBACK_HOURS` — Lookback window for analytics queries (default 24)
- `MIN_PROFIT_SCORE_ALERT` — Telegram alert when profit score reaches this level (default 70)

**Risk management:**
- `MAX_RISK_PER_TRADE` — Max balance fraction per new position (default 0.015 = 1.5%)
- `MAX_PORTFOLIO_HEAT` — Max balance fraction in open positions (default 0.30)
- `POSITION_SCALING_FACTOR` — Global position size multiplier (default 1.0)

---

## Next Development Steps (Priority)

1. ~~Update trading strategy with new strict filters (Prompt 1)~~ ✅ Done
2. ~~Implement full Paper SELL + improved PnL tracking (Prompt 2)~~ ✅ Done
3. ~~Smart items management + `items.json` (Prompt 3)~~ ✅ Done
4. ✅ Steam API price parsing for RUB currency
5. ✅ Steam 429 rate limit handling with backoff
6. ~~Risk management module (`app/risk_manager.py`)~~ ✅ Done
7. Enhanced dashboard with statistics and indicators
8. Statistics collection + weekly Telegram reports
9. State persistence and graceful shutdown
10. ✅ Docker network fix for Steam API access
11. ✅ Steam API headers updated
12. ✅ Steam cookie authentication for Docker
13. [ ] Cookie expiry detection — Telegram warning when cookies near expiry
14. ✅ Telegram timeout fix and proxy support
15. [ ] Telegram healthcheck endpoint
16. [ ] Automatic Telegram connectivity test on startup
17. [ ] Telegram circuit breaker after repeated failures
18. ✅ Auto-scanner for real Steam Market items (`app/scanner.py`)
19. [ ] Scanner dashboard statistics
20. [ ] Automatic bad-item pruning
21. ✅ Historical profitability scoring (`app/analytics.py` + `price_history.db`)
22. [ ] Price spread analytics
23. [ ] Scanner caching layer

---

**Last Updated:** May 25, 2026  
**Project Phase:** Risk management live (`RiskManager`); market intelligence scoring (`MarketAnalytics`); auto-scanner operational; dedicated price history DB; full Docker deployment with Steam cookie auth
