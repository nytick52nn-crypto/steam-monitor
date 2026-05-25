"""Startup validation for Telegram alerts."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from app.alert_store import record_alert
from app.charts import save_signal_chart
from app.config import (
    CHARTS_DIR,
    MIN_HISTORY_FOR_SIGNAL,
    STEAM_MARKET_FEE_PCT,
    TELEGRAM_VALIDATE_SIGNALS,
    telegram_config_status,
)
from app.database import SessionLocal
from app.indicators import add_indicators
from app.logger import setup_logging
from app.models import PriceHistory
from app.notifier import is_telegram_configured, send_raw_message, send_signal_alert, send_startup_test
from app.roi import calc_buy_metrics, calc_sell_metrics

log = setup_logging("telegram_validate")


def _load_any_history() -> tuple[str, pd.DataFrame] | tuple[None, None]:
    db = SessionLocal()
    try:
        row = (
            db.query(PriceHistory)
            .order_by(PriceHistory.created_at.desc())
            .first()
        )
        if not row:
            return None, None

        item_name = row.item_name
        rows = (
            db.query(PriceHistory)
            .filter(PriceHistory.item_name == item_name)
            .order_by(PriceHistory.created_at.asc())
            .all()
        )
        df = pd.DataFrame(
            {
                "created_at": [r.created_at for r in rows],
                "price": [r.price for r in rows],
                "volume": [r.volume for r in rows],
            }
        )
        df["created_at"] = pd.to_datetime(df["created_at"])
        return item_name, df
    finally:
        db.close()


def _synthetic_history(base_price: float = 3000.0, points: int = 25) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    times = [now - timedelta(hours=points - i) for i in range(points)]
    prices = [base_price + (i % 5) * 10 - (i * 2) for i in range(points)]
    return pd.DataFrame({"created_at": times, "price": prices, "volume": [50] * points})


def send_chart_test() -> bool:
    item_name, df = _load_any_history()
    if df is None or len(df) < 5:
        log.info("No DB history for chart test — using synthetic data")
        item_name = "Chart Test Item"
        df = _synthetic_history()

    df = add_indicators(df)
    df = df.dropna(subset=["rsi", "lower_band", "upper_band"])
    if df.empty:
        df = add_indicators(_synthetic_history())
        df = df.dropna(subset=["rsi", "lower_band", "upper_band"])

    chart_path = save_signal_chart(df, item_name, "TEST", CHARTS_DIR)
    text = (
        "📊 <b>Chart delivery test</b>\n\n"
        f"Item: {item_name}\n"
        "If you see this image, chart alerts work."
    )
    log.info("Sending Telegram chart test (path=%s)...", chart_path)
    ok = send_raw_message(text, chart_path)
    if ok:
        log.info("Telegram chart test: SUCCESS")
    else:
        log.error("Telegram chart test: FAILED")
    return ok


def send_signal_validation_tests() -> dict[str, bool]:
    """Send one test BUY and one test SELL alert with charts."""
    results = {"BUY": False, "SELL": False}

    item_name, df = _load_any_history()
    if df is None or len(df) < MIN_HISTORY_FOR_SIGNAL:
        item_name = "Validation | AK-47 Test"
        df = _synthetic_history(base_price=3000.0, points=30)

    df = add_indicators(df)
    df = df.dropna(subset=["rsi", "lower_band", "upper_band"])
    latest = df.iloc[-1]
    price = float(latest["price"])
    rsi = float(latest["rsi"])
    volume = int(latest.get("volume", 0))

    buy_metrics = calc_buy_metrics(price, price * 1.15, STEAM_MARKET_FEE_PCT)
    buy_chart = save_signal_chart(df, item_name, "BUY", CHARTS_DIR)
    log.info("Sending validation BUY alert...")
    results["BUY"] = send_signal_alert(
        "BUY", item_name, price, max(rsi, 25.0), buy_metrics, volume, buy_chart
    )

    sell_metrics = calc_sell_metrics(price * 0.9, price, STEAM_MARKET_FEE_PCT)
    sell_chart = save_signal_chart(df, item_name, "SELL", CHARTS_DIR)
    log.info("Sending validation SELL alert...")
    results["SELL"] = send_signal_alert(
        "SELL", item_name, price, min(rsi, 75.0), sell_metrics, volume, sell_chart
    )

    if results["BUY"]:
        record_alert(item_name, "BUY")
    if results["SELL"]:
        record_alert(item_name, "SELL")

    return results


def _check_api_reachable() -> bool:
    import requests

    from app.config import TELEGRAM_BOT_TOKEN, TELEGRAM_PROXY_URL

    proxies = {"https": TELEGRAM_PROXY_URL, "http": TELEGRAM_PROXY_URL} if TELEGRAM_PROXY_URL else None
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
            timeout=20,
            proxies=proxies,
        )
        data = r.json()
        if r.status_code == 200 and data.get("ok"):
            log.info("Telegram API reachable (bot: %s)", data.get("result", {}).get("username", "?"))
            return True
        log.error("Telegram getMe failed: %s", data)
        return False
    except Exception as exc:
        log.error(
            "Cannot reach api.telegram.org (%s). "
            "Use VPN or set TELEGRAM_PROXY_URL=socks5://host:port in .env",
            exc,
        )
        return False


def run_telegram_validation() -> bool:
    status = telegram_config_status()
    log.info("=== Telegram validation ===")
    log.info("Token: %s | Chat: %s", status["token_masked"], status["chat_id"])

    if not is_telegram_configured():
        for issue in status["issues"]:
            log.error("Telegram not ready: %s", issue)
        return False

    if not _check_api_reachable():
        return False

    startup_ok = True
    if send_startup_test():
        record_alert("__system__", "STARTUP")
    else:
        startup_ok = False

    chart_ok = send_chart_test()
    signal_results = {}
    if TELEGRAM_VALIDATE_SIGNALS:
        signal_results = send_signal_validation_tests()
        log.info("Signal validation: BUY=%s SELL=%s", signal_results.get("BUY"), signal_results.get("SELL"))

    all_ok = startup_ok and chart_ok
    if TELEGRAM_VALIDATE_SIGNALS:
        all_ok = all_ok and all(signal_results.values())

    log.info("=== Telegram validation %s ===", "PASSED" if all_ok else "FAILED")
    return all_ok
