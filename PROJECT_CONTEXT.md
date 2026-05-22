# Steam Monitor — Project Context

> **Maintenance:** After major changes (new modules, schema, env vars, Docker, signals, or dashboard), update this file in the same PR/commit. See `.cursor/rules/project-context.mdc`.

Last updated: **2026-05-22** (paper BUY / open_positions)

---

## Architecture overview

Single-container Python app that runs two processes:

1. **Price monitor** (main thread) — polls Steam Community Market API, saves prices to SQLite, evaluates trading signals, sends Telegram alerts.
2. **Streamlit dashboard** (subprocess) — reads SQLite and displays live charts/metrics on port `8501`.

```
┌─────────────────────────────────────────────────────────────┐
│  main.py                                                     │
│  ├── init DB (SQLAlchemy)                                    │
│  ├── Telegram startup validation (optional)                  │
│  ├── subprocess: streamlit run web/dashboard.py              │
│  └── run_monitor() loop                                      │
│       ├── steam_api.get_priceoverview()                      │
│       ├── monitor.save_price() → SQLite                      │
│       └── signals.evaluate_and_notify() → paper BUY + Telegram │
│  init_wallet() → SQLite wallet (singleton)                   │
│  open_positions → paper BUY rows (SELL not implemented)      │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   data/steam_cards.db            charts/*.png
   logs/monitor.log               Telegram API
```

**External APIs**

| API | Endpoint | Purpose |
|-----|----------|---------|
| Steam Market | `https://steamcommunity.com/market/priceoverview/` | `appid`, `currency`, `market_hash_name` |
| Telegram Bot | `https://api.telegram.org` | Alerts with text + chart images |

---

## Folder structure

```
steam-monitor/
├── main.py                 # Entry point: DB, dashboard, monitor loop
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env                    # Secrets & config (not committed with real tokens)
├── .env.example
├── commands.txt            # Quick command reference
├── PROJECT_CONTEXT.md      # This file
│
├── app/
│   ├── config.py           # All env vars + telegram_config_status()
│   ├── database.py         # SQLAlchemy engine + SessionLocal
│   ├── models.py           # PriceHistory, AlertSent
│   ├── logger.py           # Console + logs/monitor.log
│   ├── steam_api.py        # Steam priceoverview client (retries, delays)
│   ├── monitor.py          # Scan loop, price parsing, DB writes
│   ├── indicators.py       # RSI, EMA20, Bollinger bands
│   ├── trading_engine.py   # BUY / SELL / HOLD rules
│   ├── signals.py          # Signal evaluation + Telegram trigger
│   ├── roi.py              # Steam fee + ROI math
│   ├── charts.py           # Matplotlib signal charts (Agg backend)
│   ├── notifier.py         # Telegram send (message + photo)
│   ├── alert_store.py      # SQLite dedup for alerts
│   ├── wallet.py           # Virtual wallet: balance, deposit, withdraw
│   ├── paper_trading.py    # Paper BUY: open_positions, max size cap
│   └── telegram_validate.py # Startup / chart / BUY-SELL tests
│
├── web/
│   └── dashboard.py        # Streamlit UI
│
├── scripts/
│   ├── validate_telegram.py
│   ├── validate_wallet.py
│   ├── validate_paper_trading.py
│   └── cleanup_db.py       # Remove bad legacy price rows
│
├── data/                   # Volume: SQLite DB (host-mounted)
├── charts/                 # Volume: alert chart PNGs
└── logs/                   # Volume: monitor.log
```

---

## Docker workflow

**Image:** `python:3.11-slim`, `WORKDIR /app`, `PYTHONPATH=/app`.

**Volumes** (persist on host):

| Host path | Container path |
|-----------|----------------|
| `./data` | `/app/data` |
| `./charts` | `/app/charts` |
| `./logs` | `/app/logs` |

**Ports:** `8501:8501` (Streamlit).

**Healthcheck:** HTTP `http://127.0.0.1:8501/_stcore/health`.

**Typical commands** (Docker Desktop on Windows — add bin to PATH if needed):

```powershell
$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;$env:PATH"
docker compose up --build -d
docker compose logs -f
docker compose down
docker exec steam-monitor python scripts/validate_telegram.py
```

**Note:** `env_file: .env` is loaded at container recreate. Changing `.env` requires `docker compose up -d` (recreate), not only restart.

---

## SQLite schema

Database file: `data/steam_cards.db` (configurable via `DATA_DIR` / `DATABASE_URL`).

### `price_history`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `item_name` | STRING | Display name, indexed |
| `hash_name` | STRING | Steam market hash name, indexed |
| `price` | FLOAT | Parsed RUB (or configured currency) |
| `volume` | INTEGER | Market volume from API |
| `created_at` | DATETIME | UTC, default `utcnow` |

### `wallet`

Singleton paper-trading wallet (`id = 1`).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Always `1` |
| `balance` | FLOAT | Current balance (₽) |
| `starting_balance` | FLOAT | Initial balance from first init |
| `updated_at` | DATETIME | Last deposit/withdraw |

Created on startup via `app/wallet.init_wallet()` if missing. Initial balance from `WALLET_INITIAL_BALANCE` (default `10000`).

**API:** `get_balance()`, `deposit(amount)`, `withdraw(amount)` — withdraw raises `InsufficientBalanceError` if balance would go negative.

### `open_positions`

Paper BUY positions (SELL / close not implemented).

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | Auto-increment |
| `item_name` | STRING | Indexed; one open row per item |
| `hash_name` | STRING | Steam market hash name |
| `entry_price` | FLOAT | Fill price (₽) |
| `quantity` | FLOAT | Default `1` (one skin) |
| `cost` | FLOAT | `entry_price × quantity`; withdrawn from wallet |
| `status` | STRING | `open` (future: `closed`) |
| `signal` | STRING | `BUY` |
| `opened_at` | DATETIME | UTC, indexed |

**API:** `app/paper_trading.py` — `execute_paper_buy()`, `get_open_positions()`, `has_open_position()`.

On BUY signal transition (same cooldown gate as alerts), `execute_paper_buy()` withdraws `cost` from the wallet if:

- `PAPER_TRADING_ENABLED` is true
- No existing open position for that item
- `cost ≤ balance × MAX_POSITION_PCT / 100`
- Sufficient balance (`InsufficientBalanceError` otherwise skips)

Runs even when Telegram is not configured.

### `alert_sent`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK | |
| `item_name` | STRING | Indexed; `__system__` for startup tests |
| `signal` | STRING | `BUY`, `SELL`, `STARTUP`, etc. |
| `sent_at` | DATETIME | Indexed; used for cooldown dedup |

Tables are created via `Base.metadata.create_all()` in `main.py`.

---

## Telegram alerts logic

### Configuration gate

`app/config.telegram_config_status()` checks:

- `TELEGRAM_ENABLED`
- Non-placeholder `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`

If not ready, alerts are skipped (debug log only).

### Startup validation (`TELEGRAM_STARTUP_TEST=true`)

`app/telegram_validate.run_telegram_validation()`:

1. `getMe` API reachability check
2. Startup text message
3. Chart photo test (from DB history or synthetic data)
4. Optional test BUY + SELL (`TELEGRAM_VALIDATE_SIGNALS=true`, one-time)

### Live alerts (after each successful price save)

Flow in `app/signals.evaluate_and_notify()`:

1. Load ≥ `MIN_HISTORY_FOR_SIGNAL` rows (default 20)
2. `add_indicators()` → RSI, bands, EMA
3. `analyze_signal()` → `BUY` | `SELL` | `HOLD`
4. **Anti-spam:**
   - In-memory: skip if signal unchanged since last evaluation
   - SQLite: `should_send_signal_alert()` — same `item_name` + `signal` within `ALERT_COOLDOWN_SEC` (default 3600s)
5. **Paper BUY** (if `signal == "BUY"`): `execute_paper_buy()` — wallet withdraw + `open_positions` row
6. Build ROI via `app/roi.py` (`STEAM_MARKET_FEE_PCT`, default 15%) — Telegram only
7. `save_signal_chart()` → `charts/{item}_{SIGNAL}.png`
8. `send_signal_alert()` — HTML caption + photo via `python-telegram-bot` (skipped if Telegram not configured)

### Delivery logging

| Log | Meaning |
|-----|---------|
| `Telegram message delivered (message_id=N)` | Text OK |
| `Telegram photo:... delivered` | Chart OK |
| `Telegram ... FAILED after N attempts` | Network/token/chat error |

### Network / proxy

If `api.telegram.org` is blocked, set `TELEGRAM_PROXY_URL` (SOCKS5/HTTP). Retries: `TELEGRAM_MAX_RETRIES`, timeout: `TELEGRAM_REQUEST_TIMEOUT`.

---

## Signal engine overview

### Indicators (`app/indicators.py`)

- **EMA20** — exponential moving average of price
- **RSI(14)** — relative strength index
- **Bollinger bands** — MA20 ± 2× std20

### Rules (`app/trading_engine.py`)

| Signal | Conditions |
|--------|------------|
| **BUY** | `RSI < 30` AND `price < lower_band` |
| **SELL** | `RSI > 70` AND `price > upper_band` |
| **HOLD** | Otherwise |

### ROI for alerts (`app/roi.py`)

- **BUY:** target sell = Steam `median_price` or upper band; ROI = (net_after_fee − buy) / buy
- **SELL:** entry = min price over last 20 samples; ROI vs current sell net of fee
- **Fee:** `STEAM_MARKET_FEE_PCT` applied to gross sell price

### Config thresholds (not yet wired into `trading_engine`)

`BUY_THRESHOLD_PCT`, `SELL_THRESHOLD_PCT`, `MIN_VOLUME_PER_DAY`, `MIN_PRICE_RUB`, `MAX_PRICE_RUB` — defined in config for future filtering.

---

## Current dashboard features

**URL:** http://localhost:8501

| Feature | Implementation |
|---------|----------------|
| Metrics row | Tracked items, total records, avg latest price, last update time |
| Recent table | Last 100 `price_history` rows |
| Item selector | Dropdown by `item_name` |
| Price chart | Plotly line chart with markers (₽) |
| Latest quote | Price, volume, timestamp for selected item |
| Auto-refresh | Sidebar slider 10–120s + meta refresh |
| Manual refresh | Clears `st.cache_data`, reruns |
| Data filter | Excludes `price >= 100_000` (legacy parse errors) |
| **Virtual wallet** | Current balance, starting balance, total PnL placeholder |
| Wallet testing | Expander: deposit / withdraw (dashboard only) |
| **Open positions** | Paper BUY table via `get_open_positions()` |

Dashboard reads `price_history` via `sqlite3`; wallet and positions via SQLAlchemy helpers.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_DIR` | `data` | SQLite and data root |
| `DATABASE_URL` | `sqlite:///data/steam_cards.db` | SQLAlchemy URL |
| `STEAM_APP_ID` | `730` | CS2 (not 753) |
| `STEAM_CURRENCY` | `5` | RUB (1=USD, 3=EUR) |
| `CHECK_INTERVAL_SEC` | `60` | Scan loop sleep |
| `CHECK_INTERVAL_MIN` | `1` | Used if `CHECK_INTERVAL_SEC` unset |
| `STEAM_REQUEST_DELAY_MIN` | `2` | Min delay between Steam calls |
| `STEAM_REQUEST_DELAY_MAX` | `5` | Max delay between Steam calls |
| `TELEGRAM_BOT_TOKEN` | — | BotFather token |
| `TELEGRAM_CHAT_ID` | — | Numeric chat ID |
| `TELEGRAM_ENABLED` | `true` | Master switch |
| `TELEGRAM_STARTUP_TEST` | `true` | Run validation on boot |
| `TELEGRAM_VALIDATE_SIGNALS` | `false` | Send test BUY/SELL once |
| `TELEGRAM_PROXY_URL` | — | Optional proxy for Telegram API |
| `TELEGRAM_REQUEST_TIMEOUT` | `60` | HTTP timeout (seconds) |
| `TELEGRAM_MAX_RETRIES` | `3` | Send retries |
| `STEAM_MARKET_FEE_PCT` | `15` | Fee on sale for ROI |
| `MIN_HISTORY_FOR_SIGNAL` | `20` | Min DB rows before signals |
| `ALERT_COOLDOWN_SEC` | `3600` | Per item+signal dedup window |
| `CHARTS_DIR` | `charts` | Alert chart output |
| `SCAN_TOTAL_ITEMS` | `300` | Planned scan size (not used yet) |
| `BUY_THRESHOLD_PCT` | `15` | Future strategy filter |
| `SELL_THRESHOLD_PCT` | `20` | Future strategy filter |
| `MIN_VOLUME_PER_DAY` | `10` | Future strategy filter |
| `MIN_PRICE_RUB` | `3` | Future strategy filter |
| `MAX_PRICE_RUB` | `300` | Future strategy filter |
| `WALLET_INITIAL_BALANCE` | `10000` | Virtual wallet starting balance (₽) |
| `PAPER_TRADING_ENABLED` | `true` | Execute paper BUY on BUY signal |
| `MAX_POSITION_PCT` | `10` | Max single BUY cost as % of wallet balance |

Copy `.env.example` → `.env` and fill secrets.

---

## Important terminal commands

```powershell
# Docker (Windows PATH fix)
$env:PATH = "C:\Program Files\Docker\Docker\resources\bin;$env:PATH"

docker compose up --build -d
docker compose logs -f
docker compose ps
docker compose down

# Telegram validation only
docker exec steam-monitor python scripts/validate_telegram.py

# DB inspection
docker exec steam-monitor python -c "import sqlite3; c=sqlite3.connect('/app/data/steam_cards.db'); print(c.execute('SELECT COUNT(*) FROM price_history').fetchone())"

# Cleanup bad legacy prices
docker exec steam-monitor python /app/scripts/cleanup_db.py

# Config status
docker exec steam-monitor python -c "from app.config import telegram_config_status; print(telegram_config_status())"

# Wallet validation
docker exec steam-monitor python scripts/validate_wallet.py

# Paper trading validation
docker exec steam-monitor python scripts/validate_paper_trading.py
```

---

## Trading strategy overview

**Goal:** Detect short-term mean-reversion opportunities on Steam CS2 market items using price history built by the monitor.

**Current approach (technical):**

1. Collect `lowest_price` / `median_price` on a fixed item list (`TEST_ITEMS` in `monitor.py`).
2. When price is statistically low (below lower Bollinger band) and RSI oversold → **BUY** alert.
3. When price is high (above upper band) and RSI overbought → **SELL** alert.
4. Alerts include estimated ROI after Steam’s ~15% market fee.
5. **Paper BUY** on BUY transition: deducts balance, stores `open_positions` (no automated SELL yet).

**Planned strategy extensions (config exists, code pending):**

- Filter by `MIN_VOLUME_PER_DAY`, price range `MIN_PRICE_RUB`–`MAX_PRICE_RUB`
- Percent dip/rally thresholds `BUY_THRESHOLD_PCT` / `SELL_THRESHOLD_PCT`
- Expand beyond `TEST_ITEMS` to `SCAN_TOTAL_ITEMS` market scan

**Risks:** Steam rate limits, API timeouts, regional blocks on Telegram, manual execution on Steam market.

---

## Current roadmap

| Priority | Task | Status |
|----------|------|--------|
| P0 | Steam API + SQLite + dashboard | Done |
| P0 | Telegram BUY/SELL + charts + dedup | Done |
| P1 | Virtual wallet (balance, deposit, withdraw) | Done |
| P1 | Paper BUY + `open_positions` + dashboard table | Done |
| P1 | Paper SELL / close positions | Not started |
| P1 | Expand item list / market scanner | Planned |
| P1 | Wire `BUY_THRESHOLD_PCT` / volume filters into engine | Planned |
| P2 | Persist signal state across restarts | Partial (`alert_sent` only) |
| P2 | Dashboard: RSI/bands overlay, signal markers | Planned |
| P3 | Auto-trade (real Steam) | Not started |
| P3 | Multi-currency / non-RUB parsing | Partial |

---

## Known issues

| Issue | Impact | Workaround |
|-------|--------|------------|
| `api.telegram.org` blocked on some networks | Telegram timeouts | VPN or `TELEGRAM_PROXY_URL` |
| Steam SSL/read timeouts | Missed items in a cycle | Retries in `steam_api.py` (3×, 30s) |
| `руб.` suffix leaves stray `.` if stripped wrong | Was inflating prices 100× | Fixed in `parse_price()` — strip currency before parsing |
| Legacy bad rows in DB (e.g. `299373`) | Chart spikes | `cleanup_db.py` or dashboard filter `< 100000` |
| `TEST_ITEMS` hardcoded | Only 3 items tracked | Edit `monitor.py` or implement scanner |
| `SCAN_TOTAL_ITEMS` unused | Config misleading | Roadmap |
| Docker not in system PATH (Windows) | `docker` not found | Use full path to `Docker\resources\bin` |
| Startup validation slows boot ~20s when Telegram slow | Delay before first scan | Set `TELEGRAM_STARTUP_TEST=false` after validation |
| `.env` not hot-reloaded | Old credentials in container | `docker compose up -d` after `.env` change |

---

## Key modules quick reference

| Module | Responsibility |
|--------|----------------|
| `steam_api.py` | `get_priceoverview()`, appid 730, retries |
| `monitor.py` | Main loop, `parse_price()`, `save_price()` |
| `signals.py` | Indicators + paper BUY + notify pipeline |
| `paper_trading.py` | `execute_paper_buy()`, position queries |
| `notifier.py` | Telegram HTML + photos |
| `telegram_validate.py` | Boot-time self-test |
| `alert_store.py` | Cooldown dedup in SQLite |
| `web/dashboard.py` | Streamlit UI |

---

*End of project context.*
