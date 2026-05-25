import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_db_file = (DATA_DIR / "steam_cards.db").as_posix()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_db_file}")

# 730 = Counter-Strike 2
STEAM_APP_ID = int(os.getenv("STEAM_APP_ID", 730))
# 5 = RUB, 1 = USD, 3 = EUR
STEAM_CURRENCY = int(os.getenv("STEAM_CURRENCY", 5))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() in ("1", "true", "yes")
TELEGRAM_STARTUP_TEST = os.getenv("TELEGRAM_STARTUP_TEST", "true").lower() in ("1", "true", "yes")
TELEGRAM_VALIDATE_SIGNALS = os.getenv("TELEGRAM_VALIDATE_SIGNALS", "false").lower() in (
    "1", "true", "yes",
)
_PLACEHOLDER_TOKENS = {"YOUR_BOT_TOKEN", "your_bot_token", ""}
_PLACEHOLDER_CHATS = {"YOUR_CHAT_ID", "your_chat_id", ""}


def _mask_token(token: str) -> str:
    if not token or len(token) < 10:
        return "(not set)"
    return f"{token[:6]}...{token[-4:]}"


def telegram_config_status() -> dict:
    issues = []
    token_loaded = bool(TELEGRAM_BOT_TOKEN) and TELEGRAM_BOT_TOKEN not in _PLACEHOLDER_TOKENS
    chat_loaded = bool(TELEGRAM_CHAT_ID) and TELEGRAM_CHAT_ID not in _PLACEHOLDER_CHATS
    if not TELEGRAM_ENABLED:
        issues.append("TELEGRAM_ENABLED is false")
    if not token_loaded:
        issues.append("TELEGRAM_BOT_TOKEN missing or placeholder")
    if not chat_loaded:
        issues.append("TELEGRAM_CHAT_ID missing or placeholder")
    ready = TELEGRAM_ENABLED and token_loaded and chat_loaded
    return {
        "enabled": TELEGRAM_ENABLED,
        "token_loaded": token_loaded,
        "token_masked": _mask_token(TELEGRAM_BOT_TOKEN),
        "chat_loaded": chat_loaded,
        "chat_id": TELEGRAM_CHAT_ID if chat_loaded else "(not set)",
        "ready": ready,
        "issues": issues,
    }


CHARTS_DIR = Path(os.getenv("CHARTS_DIR", "charts"))
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# CS2 market: ~15% total (5% Steam + 10% game)
STEAM_MARKET_FEE_PCT = float(os.getenv("STEAM_MARKET_FEE_PCT", 15))

MIN_HISTORY_FOR_SIGNAL = int(os.getenv("MIN_HISTORY_FOR_SIGNAL", 20))
ALERT_COOLDOWN_SEC = int(os.getenv("ALERT_COOLDOWN_SEC", 3600))
AUTO_SCAN_ENABLED = os.getenv(
    "AUTO_SCAN_ENABLED", "false"
).lower() in ("1", "true", "yes")

AUTO_SCAN_INTERVAL_HOURS = int(
    os.getenv("AUTO_SCAN_INTERVAL_HOURS", "24")
)

SCAN_TOTAL_ITEMS = int(
    os.getenv("SCAN_TOTAL_ITEMS", "50")
)

SCANNER_REQUEST_DELAY = float(
    os.getenv("SCANNER_REQUEST_DELAY", "5")
)

CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", 1))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", CHECK_INTERVAL_MIN * 60))

# --- Trading strategy thresholds ---
BUY_THRESHOLD_PCT = float(os.getenv("BUY_THRESHOLD_PCT", 22))
SELL_THRESHOLD_PCT = float(os.getenv("SELL_THRESHOLD_PCT", 20))
MIN_PROFIT_PCT = float(os.getenv("MIN_PROFIT_PCT", 15))
SELL_PROFIT_PCT = float(os.getenv("SELL_PROFIT_PCT", 14))
MIN_VOLUME_PER_DAY = int(
    os.getenv("MIN_VOLUME_PER_DAY", "20")
)

MIN_PRICE_RUB = float(
    os.getenv("MIN_PRICE_RUB", "50")
)

MAX_PRICE_RUB = float(
    os.getenv("MAX_PRICE_RUB", "5000")
)

# --- Steam API delays (seconds between requests) ---
# Keep at 10-20s to avoid 429 rate limit bans from Steam
STEAM_REQUEST_DELAY_MIN = float(os.getenv("STEAM_REQUEST_DELAY_MIN", 10))
STEAM_REQUEST_DELAY_MAX = float(os.getenv("STEAM_REQUEST_DELAY_MAX", 20))

# Items file
ITEMS_FILE = os.getenv("ITEMS_FILE", "data/items.json")

# Virtual wallet
WALLET_INITIAL_BALANCE = float(os.getenv("WALLET_INITIAL_BALANCE", 10000))

# Paper trading
PAPER_TRADING_ENABLED = os.getenv("PAPER_TRADING_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", 10))

# --- DRY_RUN mode ---
# true  = бот только логирует сигналы, не открывает paper позиции
# false = бот открывает paper позиции при сигнале
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("1", "true", "yes")

STEAM_SESSION_COOKIE = os.getenv("STEAM_SESSION_COOKIE", "").strip()
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE", "").strip()

TELEGRAM_REQUEST_TIMEOUT = float(
    os.getenv("TELEGRAM_REQUEST_TIMEOUT", "15")
)

TELEGRAM_PROXY_URL = (
    os.getenv("TELEGRAM_PROXY_URL", "").strip() or None
)

TELEGRAM_RETRY_DELAY = float(
    os.getenv("TELEGRAM_RETRY_DELAY", "3")
)

TELEGRAM_MAX_RETRIES = int(
    os.getenv("TELEGRAM_MAX_RETRIES", "3")
)

# --- Dedicated price history DB (analytics / trend detection) ---
PRICE_HISTORY_DB = os.getenv(
    "PRICE_HISTORY_DB",
    "data/price_history.db",
)
PRICE_HISTORY_RETENTION_DAYS = int(
    os.getenv("PRICE_HISTORY_RETENTION_DAYS", "30")
)