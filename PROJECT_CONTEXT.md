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

## Current Status (as of May 25, 2026)

**Production-ready stack:**
- ✅ **3-service Docker Compose** — monitor loop, FastAPI backend, React+Nginx frontend
- ✅ **Professional monitoring panel** — dashboard KPIs, opportunities table, watchlist, positions, trades, backtests, system health, live logs (REST + WebSocket)
- ✅ **Risk management** — `RiskManager` gates paper BUYs and sizes positions
- ✅ **Market analytics** — `MarketAnalytics` + dedicated `price_history.db`
- ✅ **Auto-scanner** — discovers liquid CS2 items (`app/scanner.py`)
- ✅ **Steam cookie auth** for Docker (session cookies in existing `.env`)
- ✅ **Frontend TypeScript build** passes in Docker (`tsc -b && vite build`)

**Core monitor (completed):**
- SQLite + SQLAlchemy, Steam API client, indicators, signals, paper trading, Telegram alerts
- Steam 429 backoff, RUB price parsing, median_price fallback
- Streamlit dashboard (`web/dashboard.py`) — legacy, still available

**In progress / next:**
- Cookie expiry detection + Telegram warning
- Telegram healthcheck / startup connectivity test
- Enhanced Streamlit dashboard parity with React panel
- State persistence and graceful shutdown
- Full strict "High-Quality Mean Reversion" filter rollout in `trading_engine.py`

---

## Architecture Overview

### Docker (Multi-Container)

Three-service Docker Compose stack — one command starts the full system:

| Service          | Container               | Dockerfile             | Port(s)   | Purpose                         |
|------------------|-------------------------|------------------------|-----------|---------------------------------|
| `steam-monitor`  | `steam-monitor`         | `Dockerfile`           | —         | Main Python monitor loop        |
| `backend`        | `steam-monitor-backend` | `Dockerfile.backend`   | `8000`    | FastAPI REST + WebSocket `/ws`  |
| `frontend`       | `steam-monitor-frontend`| `Dockerfile.frontend`  | `5173:80` | React SPA (Nginx + API proxy)   |

**Networking & data:**
- Bridge network `steam-network`; services resolve each other by container name.
- Bind mounts: `./data`, `./logs`, `./charts` (monitor); `./data`, `./logs` (backend).
- All services load the **existing** project `.env` via `env_file: .env` (never recreate or commit).
- Nginx in `frontend` proxies `/api/` and `/ws` → `steam-monitor-backend:8000` (`nginx.conf`).
- Backend healthcheck uses Python `urllib` (no extra `curl` package in image).

**How to Run (Docker):**
```bash
# Stop, rebuild, and start all services
docker-compose down && docker-compose up -d --build

# Check status
docker-compose ps

# Follow logs
docker-compose logs -f steam-monitor
docker-compose logs -f backend
docker-compose logs -f frontend
```

**URLs:**
- Monitoring panel: http://localhost:5173
- API docs / health: http://localhost:8000/api/health , http://localhost:8000/docs

**Main Components:**
- `main.py` → Entry point (starts dashboard and/or monitor)
- `app/` → Core business logic
- `web/` → Streamlit dashboard (legacy)
- `backend/` → FastAPI monitoring panel API + WebSocket
- `frontend/` → React + TypeScript monitoring UI (Vite)
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
├── Dockerfile                       # Monitor container
├── Dockerfile.backend               # FastAPI container
├── Dockerfile.frontend              # React + Nginx container
├── docker-compose.yml               # 4-service stack
├── nginx.conf                       # Frontend reverse proxy config
├── requirements.txt
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
│   └── dashboard.py                 # Streamlit UI (legacy)
│
├── backend/                         # FastAPI monitoring panel
│   ├── main.py
│   ├── deps.py
│   ├── websocket.py
│   ├── utils.py
│   ├── api/router.py
│   ├── api/endpoints/               # analytics, positions, trades, backtests, system, logs
│   └── schemas/                     # Pydantic v2 models
│
├── frontend/                        # React + TypeScript (Vite)
│   ├── src/components/              # Dashboard, tables, modal, logs, heat gauge
│   ├── src/hooks/
│   ├── src/types/
│   └── package.json
│
├── run_backend.sh / .bat            # Start API on :8000
├── run_frontend.sh / .bat           # Start UI on :5173
│
├── charts/                          # Generated chart images
└── logs/
text


---

## Professional Monitoring Web Panel (FastAPI + React)

Standalone dashboard for operators: dark theme, KPI cards, advanced opportunities table, item detail charts, watchlist, positions with heat gauge, trade history + CSV export, backtesting UI, system health and live logs. All data is read from existing `app/*` modules and SQLite (`steam_cards.db`, `price_history.db`) — no duplicate business logic.

**Stack:** FastAPI + WebSocket (`/ws`), React 18 + TypeScript, TanStack Query, Recharts, Tailwind CSS.

**API base:** `http://127.0.0.1:8000/api`  
**WebSocket:** `ws://127.0.0.1:8000/ws` (15s snapshot push: opportunities, positions, log tail)

| Area | Endpoints |
|------|-----------|
| Dashboard KPIs | `GET /api/system/dashboard` |
| Opportunities | `GET /api/analytics/opportunities` (search, multi-filter, sort, pagination) |
| Item detail | `GET /api/analytics/items/{name}/detail`, `/history?days=7\|30\|90`, `/risk` |
| Watchlist | `GET/POST/DELETE /api/analytics/watchlist/{item}` → `data/watchlist.json` |
| Filter presets | `GET/POST /api/analytics/filter-presets` → `data/filter_presets.json` |
| Positions | `GET /api/positions`, `GET /api/positions/summary` |
| Trades | `GET /api/trades`, `GET /api/trades/export` (CSV) |
| Backtests | `POST /api/backtests/run`, `GET /api/backtests` (history in `data/backtest_history.json`) |
| System | `GET /api/system/health` |
| Logs | `GET /api/logs` (tail `logs/monitor.log`) |
| Actions | `POST /api/analytics/run` (same as monitor analytics cycle) |

### Run instructions (local, uses existing `.env` only)

**1. Install Python deps** (from repo root):

```bash
pip install -r requirements.txt
```

**2. Backend** (port 8000):

```bash
# Linux/macOS
./run_backend.sh

# Windows
run_backend.bat
```

**3. Frontend** (port 5173, proxies `/api` and `/ws` to backend):

```bash
# Linux/macOS
./run_frontend.sh

# Windows
run_frontend.bat
```

Open **http://localhost:5173**. Ensure `main.py` monitor (or Docker `steam-monitor`) is running so `price_history.db` and `logs/monitor.log` stay fresh.

**Production-style (optional):** build UI then serve from FastAPI:

```bash
cd frontend && npm run build
# backend/main.py mounts frontend/dist at / when present
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

**Usability highlights:** global item search; profit/liquidity/volatility/momentum/price filters; column visibility; saved filter presets; row click → modal with 7/30/90d price+volume chart and profit-score breakdown; watchlist tab; portfolio heat gauge; real-time PnL on open positions; dynamic stop-loss display; trade filters + CSV export; backtest form + history; system health indicators; log viewer with pause, level filter, search; refresh 15s / 30s / 60s / manual.

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

## Roadmap (Priority)

| Status | Item |
|--------|------|
| ✅ | Paper trading BUY/SELL + PnL, smart `items.json`, Steam RUB parsing & 429 backoff |
| ✅ | Risk management (`app/risk_manager.py`) |
| ✅ | Price history DB + `MarketAnalytics` scoring |
| ✅ | Auto-scanner (`app/scanner.py`) |
| ✅ | FastAPI + React monitoring panel (`backend/`, `frontend/`) |
| ✅ | Docker 3-service stack with Nginx API proxy |
| ✅ | Telegram timeout + optional proxy |
| [ ] | Cookie expiry detection → Telegram warning |
| [ ] | Telegram healthcheck + startup connectivity test |
| [ ] | Strict mean-reversion filters fully enforced in live signals |
| [ ] | Weekly Telegram performance digest |
| [ ] | State persistence + graceful monitor shutdown |
| [ ] | Scanner stats UI, bad-item pruning, scanner cache |
| [ ] | Price spread analytics; history-backed Streamlit charts |

---

**Last Updated:** May 25, 2026  
**Project Phase:** Docker stack production-ready; FastAPI+React panel is the primary operator UI; monitor + analytics + risk management operational
