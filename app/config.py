import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

_db_file = (DATA_DIR / "steam_cards.db").as_posix()
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_db_file}")

# 730 = Counter-Strike 2; 753 = Steam trading cards (wrong for skins)
STEAM_APP_ID = int(os.getenv("STEAM_APP_ID", 730))
# 5 = RUB, 1 = USD, 3 = EUR
STEAM_CURRENCY = int(os.getenv("STEAM_CURRENCY", 5))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() in ("1", "true", "yes")
TELEGRAM_STARTUP_TEST = os.getenv("TELEGRAM_STARTUP_TEST", "true").lower() in ("1", "true", "yes")
TELEGRAM_VALIDATE_SIGNALS = os.getenv("TELEGRAM_VALIDATE_SIGNALS", "false").lower() in (
    "1",
    "true",
    "yes",
)
TELEGRAM_PROXY_URL = os.getenv("TELEGRAM_PROXY_URL", "").strip() or None
TELEGRAM_REQUEST_TIMEOUT = float(os.getenv("TELEGRAM_REQUEST_TIMEOUT", 60))
TELEGRAM_MAX_RETRIES = int(os.getenv("TELEGRAM_MAX_RETRIES", 3))

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

SCAN_TOTAL_ITEMS = int(os.getenv("SCAN_TOTAL_ITEMS", 300))
CHECK_INTERVAL_MIN = int(os.getenv("CHECK_INTERVAL_MIN", 1))
CHECK_INTERVAL_SEC = int(os.getenv("CHECK_INTERVAL_SEC", CHECK_INTERVAL_MIN * 60))

BUY_THRESHOLD_PCT = float(os.getenv("BUY_THRESHOLD_PCT", 15))
SELL_THRESHOLD_PCT = float(os.getenv("SELL_THRESHOLD_PCT", 20))

MIN_VOLUME_PER_DAY = int(os.getenv("MIN_VOLUME_PER_DAY", 10))
MIN_PRICE_RUB = float(os.getenv("MIN_PRICE_RUB", 3))
MAX_PRICE_RUB = float(os.getenv("MAX_PRICE_RUB", 300))

STEAM_REQUEST_DELAY_MIN = float(os.getenv("STEAM_REQUEST_DELAY_MIN", 2))
STEAM_REQUEST_DELAY_MAX = float(os.getenv("STEAM_REQUEST_DELAY_MAX", 5))

# Virtual wallet (paper trading balance, no real Steam funds)
WALLET_INITIAL_BALANCE = float(os.getenv("WALLET_INITIAL_BALANCE", 10000))

# Paper trading (BUY only; SELL not implemented yet)
PAPER_TRADING_ENABLED = os.getenv("PAPER_TRADING_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_POSITION_PCT = float(os.getenv("MAX_POSITION_PCT", 10))