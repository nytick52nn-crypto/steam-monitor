import pandas as pd
from sqlalchemy.orm import Session

from app.alert_store import record_alert, should_send_signal_alert
from app.charts import save_signal_chart
from app.config import (
    CHARTS_DIR,
    MIN_HISTORY_FOR_SIGNAL,
    STEAM_MARKET_FEE_PCT,
)
from app.database import SessionLocal
from app.indicators import add_indicators
from app.logger import setup_logging
from app.models import PriceHistory
from app.notifier import is_telegram_configured, send_signal_alert
from app.paper_trading import execute_paper_buy
from app.roi import calc_buy_metrics, calc_sell_metrics
from app.trading_engine import analyze_signal

log = setup_logging("signals")

# In-memory last evaluated signal (HOLD/BUY/SELL) — prevents re-firing while state unchanged
_last_evaluated: dict[str, str] = {}


def load_price_history(item_name: str, db: Session) -> pd.DataFrame:
    rows = (
        db.query(PriceHistory)
        .filter(PriceHistory.item_name == item_name)
        .order_by(PriceHistory.created_at.asc())
        .all()
    )
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(
        {
            "created_at": [r.created_at for r in rows],
            "price": [r.price for r in rows],
            "volume": [r.volume for r in rows],
        }
    )
    df["created_at"] = pd.to_datetime(df["created_at"])
    return df


def evaluate_and_notify(
    item_name: str,
    current_price: float,
    volume: int,
    median_price: float | None = None,
) -> str | None:
    db = SessionLocal()
    try:
        df = load_price_history(item_name, db)
    finally:
        db.close()

    if len(df) < MIN_HISTORY_FOR_SIGNAL:
        log.debug(
            "Not enough history for %s (%d/%d)",
            item_name,
            len(df),
            MIN_HISTORY_FOR_SIGNAL,
        )
        return None

    df = add_indicators(df)
    df = df.dropna(subset=["rsi", "lower_band", "upper_band"])
    if df.empty:
        return None

    signal = analyze_signal(df)
    prev_signal = _last_evaluated.get(item_name, "HOLD")
    _last_evaluated[item_name] = signal

    if signal not in ("BUY", "SELL"):
        return signal

    # Only act on transition into BUY/SELL (not every scan while condition holds)
    if signal == prev_signal:
        log.debug("Signal unchanged for %s (%s), skipping", item_name, signal)
        return signal

    if not should_send_signal_alert(item_name, signal):
        return signal

    if signal == "BUY":
        position = execute_paper_buy(item_name, current_price)
        if position:
            log.info("Paper position opened for %s (id=%s)", item_name, position.id)

    if not is_telegram_configured():
        return signal

    latest = df.iloc[-1]
    rsi = float(latest["rsi"])

    if signal == "BUY":
        target = float(median_price or latest["upper_band"] or latest["ema20"])
        metrics = calc_buy_metrics(current_price, target, STEAM_MARKET_FEE_PCT)
    else:
        entry = float(df["price"].tail(20).min())
        metrics = calc_sell_metrics(entry, current_price, STEAM_MARKET_FEE_PCT)

    chart_path = save_signal_chart(df, item_name, signal, CHARTS_DIR)

    if send_signal_alert(
        signal=signal,
        item_name=item_name,
        price=current_price,
        rsi=rsi,
        metrics=metrics,
        volume=volume,
        chart_path=chart_path,
    ):
        record_alert(item_name, signal)
        log.info("Alert recorded: %s %s", item_name, signal)

    return signal
