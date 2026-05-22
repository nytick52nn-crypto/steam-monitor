"""Trading signal engine — High-Quality Mean Reversion strategy."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.config import (
    BUY_THRESHOLD_PCT,
    MAX_PRICE_RUB,
    MIN_PRICE_RUB,
    MIN_PROFIT_PCT,
    MIN_VOLUME_PER_DAY,
    SELL_PROFIT_PCT,
    STEAM_MARKET_FEE_PCT,
)
from app.roi import calc_buy_metrics


# ── helpers ──────────────────────────────────────────────────────────────


def _is_valid(value: Any) -> bool:
    """Return True if *value* is a finite number (not NaN / None / inf)."""
    if value is None:
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _hold(reason: str) -> dict:
    return {
        "signal": "HOLD",
        "reasoning": [reason],
        "estimated_profit_pct": 0.0,
        "confidence": 0.0,
    }


# ── public API ───────────────────────────────────────────────────────────


def get_detailed_trade_signal(
    df: pd.DataFrame,
    current_price: float,
    volume: int,
    fee_pct: float = STEAM_MARKET_FEE_PCT,
    entry_price: float | None = None,
) -> dict:
    """Evaluate the latest row of *df* against the High-Quality Mean Reversion
    strategy and return a detailed result dict.

    Parameters
    ----------
    df : DataFrame with columns added by ``indicators.add_indicators``
         (price, rsi, ema20, ma20, lower_band, upper_band).
    current_price : latest market price (RUB).
    volume : 24-h sales volume reported by Steam.
    fee_pct : Steam Market total fee (default from config).
    entry_price : paper-trade entry price (required to evaluate SELL on
                  realized-profit basis; ``None`` means no open position).

    Returns
    -------
    dict with keys:
        signal : "BUY" | "SELL" | "HOLD"
        reasoning : list[str]
        estimated_profit_pct : float
        confidence : float  (0.0 – 1.0)
    """

    if df.empty:
        return _hold("No indicator data")

    latest = df.iloc[-1]

    rsi = latest.get("rsi")
    ema20 = latest.get("ema20")
    lower_band = latest.get("lower_band")
    upper_band = latest.get("upper_band")
    ma20 = latest.get("ma20")

    if not all(_is_valid(v) for v in (rsi, ema20, lower_band, upper_band, ma20)):
        return _hold("Required indicators (RSI/BB/EMA20) not available or NaN")

    rsi = float(rsi)
    ema20 = float(ema20)
    lower_band = float(lower_band)
    upper_band = float(upper_band)
    ma20 = float(ma20)  # middle Bollinger band

    # ── SELL evaluation (checked first so open positions are managed) ─────
    if entry_price is not None and entry_price > 0:
        sell_reasons: list[str] = []
        sell_metrics = calc_buy_metrics(entry_price, current_price, fee_pct)
        realized_profit = sell_metrics.roi_pct

        if rsi >= 68:
            sell_reasons.append(f"RSI {rsi:.1f} >= 68 (overbought)")
        if current_price >= upper_band:
            sell_reasons.append(
                f"Price {current_price:.2f} >= Upper BB {upper_band:.2f}"
            )
        if realized_profit >= SELL_PROFIT_PCT:
            sell_reasons.append(
                f"Realized profit {realized_profit:.1f}% >= {SELL_PROFIT_PCT}%"
            )

        if sell_reasons:
            return {
                "signal": "SELL",
                "reasoning": sell_reasons,
                "estimated_profit_pct": round(realized_profit, 2),
                "confidence": min(1.0, len(sell_reasons) / 3.0),
            }

    # ── BUY evaluation ───────────────────────────────────────────────────
    buy_checks: list[tuple[bool, str, str]] = []

    buy_checks.append((
        rsi <= 35,
        f"RSI {rsi:.1f} <= 35 (oversold) ✓",
        f"RSI {rsi:.1f} > 35 (not oversold)",
    ))

    buy_checks.append((
        current_price < lower_band,
        f"Price {current_price:.2f} < Lower BB {lower_band:.2f} ✓",
        f"Price {current_price:.2f} >= Lower BB {lower_band:.2f}",
    ))

    deviation = abs(current_price - ema20) / ema20 * 100 if ema20 > 0 else 0.0
    buy_checks.append((
        deviation >= BUY_THRESHOLD_PCT,
        f"EMA20 deviation {deviation:.1f}% >= {BUY_THRESHOLD_PCT}% ✓",
        f"EMA20 deviation {deviation:.1f}% < {BUY_THRESHOLD_PCT}%",
    ))

    buy_checks.append((
        volume >= MIN_VOLUME_PER_DAY,
        f"Volume {volume} >= {MIN_VOLUME_PER_DAY} ✓",
        f"Volume {volume} < {MIN_VOLUME_PER_DAY} (low liquidity)",
    ))

    buy_checks.append((
        MIN_PRICE_RUB <= current_price <= MAX_PRICE_RUB,
        f"Price {current_price:.2f} in [{MIN_PRICE_RUB}–{MAX_PRICE_RUB}] ✓",
        f"Price {current_price:.2f} outside [{MIN_PRICE_RUB}–{MAX_PRICE_RUB}]",
    ))

    expected_exit = max(ema20, ma20)
    metrics = calc_buy_metrics(current_price, expected_exit, fee_pct)
    estimated_profit = metrics.roi_pct

    buy_checks.append((
        estimated_profit >= MIN_PROFIT_PCT,
        f"Est. net profit {estimated_profit:.1f}% >= {MIN_PROFIT_PCT}% ✓",
        f"Est. net profit {estimated_profit:.1f}% < {MIN_PROFIT_PCT}%",
    ))

    passed = [ok for ok, _, _ in buy_checks]
    all_passed = all(passed)

    if all_passed:
        reasoning = [ok_msg for _, ok_msg, _ in buy_checks]
        confidence = 1.0
        return {
            "signal": "BUY",
            "reasoning": reasoning,
            "estimated_profit_pct": round(estimated_profit, 2),
            "confidence": confidence,
        }

    # ── HOLD — explain which BUY conditions failed ───────────────────────
    failed_reasons = [fail_msg for ok, _, fail_msg in buy_checks if not ok]
    return {
        "signal": "HOLD",
        "reasoning": failed_reasons,
        "estimated_profit_pct": round(estimated_profit, 2),
        "confidence": 0.0,
    }


# ── backward-compatible wrapper ─────────────────────────────────────────


def analyze_signal(df: pd.DataFrame) -> str:
    """Legacy interface kept for backward compatibility.

    Returns one of ``"BUY"``, ``"SELL"``, ``"HOLD"``.
    """
    if df.empty:
        return "HOLD"
    latest = df.iloc[-1]
    price = float(latest["price"])
    volume = int(latest.get("volume", 0))
    result = get_detailed_trade_signal(df, price, volume)
    return result["signal"]
