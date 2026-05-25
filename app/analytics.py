"""Historical profitability analytics from dedicated price_history.db (read-only)."""

from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from app.config import (
    ANALYTICS_LOOKBACK_HOURS,
    MIN_HISTORY_SNAPSHOTS,
    MIN_PROFIT_SCORE_ALERT,
    PRICE_HISTORY_DB,
)
from app.logger import setup_logging

log = setup_logging("analytics")

_READ_TIMEOUT_SEC = 5.0
_MAX_CANDIDATES = 80
_LIQUIDITY_HIGH_VOL = 80
_LIQUIDITY_MED_VOL = 30


def _clamp_score(value: float) -> float:
    return max(0.0, min(100.0, value))


def _label_from_score(score: float, high: str, mid: str, low: str) -> str:
    if score >= 65:
        return high
    if score >= 35:
        return mid
    return low


class MarketAnalytics:
    """Scores Steam Market items using SQLite price history (no network calls)."""

    def __init__(
        self,
        lookback_hours: int | None = None,
        min_snapshots: int | None = None,
    ) -> None:
        self.lookback_hours = lookback_hours or ANALYTICS_LOOKBACK_HOURS
        self.min_snapshots = min_snapshots or MIN_HISTORY_SNAPSHOTS

    def _db_path(self) -> Path:
        return Path(PRICE_HISTORY_DB)

    def _lookback_param(self, hours: int | None = None) -> str:
        h = self.lookback_hours if hours is None else hours
        return f"-{int(h)} hours"

    def _connect(self) -> sqlite3.Connection | None:
        path = self._db_path()
        if not path.is_file():
            log.debug("Price history DB not found: %s", path)
            return None
        try:
            conn = sqlite3.connect(
                f"file:{path.resolve()}?mode=ro",
                uri=True,
                timeout=_READ_TIMEOUT_SEC,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA query_only=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            return conn
        except Exception as exc:
            log.error("Analytics DB connect failed: %s", exc)
            return None

    def get_price_history(
        self, item_name: str, hours: int | None = None
    ) -> list[dict]:
        """Return recent snapshots for one item (indexed range query)."""
        conn = self._connect()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT price, volume, timestamp
                FROM price_history
                WHERE item_name = ?
                  AND timestamp >= datetime('now', ?)
                ORDER BY timestamp ASC
                """,
                (item_name, self._lookback_param(hours)),
            ).fetchall()
            return [
                {
                    "price": float(r["price"]),
                    "volume": int(r["volume"]) if r["volume"] is not None else 0,
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
        except Exception as exc:
            log.error("get_price_history failed for %s: %s", item_name, exc)
            return []
        finally:
            conn.close()

    def _snapshot_count(self, item_name: str, hours: int | None = None) -> int:
        conn = self._connect()
        if conn is None:
            return 0
        try:
            row = conn.execute(
                """
                SELECT COUNT(*) AS n
                FROM price_history
                WHERE item_name = ?
                  AND timestamp >= datetime('now', ?)
                """,
                (item_name, self._lookback_param(hours)),
            ).fetchone()
            return int(row["n"]) if row else 0
        except Exception as exc:
            log.error("snapshot count failed for %s: %s", item_name, exc)
            return 0
        finally:
            conn.close()

    def _has_sufficient_data(self, item_name: str, hours: int | None = None) -> bool:
        return self._snapshot_count(item_name, hours) >= self.min_snapshots

    @staticmethod
    def _prices_from_history(history: list[dict]) -> list[float]:
        return [h["price"] for h in history if h.get("price") is not None]

    @staticmethod
    def _volumes_from_history(history: list[dict]) -> list[int]:
        return [max(0, int(h.get("volume") or 0)) for h in history]

    def calculate_volatility(self, item_name: str) -> float | None:
        """0–100 score; moderate volatility scores highest."""
        history = self.get_price_history(item_name)
        if len(history) < self.min_snapshots:
            return None
        prices = self._prices_from_history(history)
        if len(prices) < 2:
            return None
        mean = sum(prices) / len(prices)
        if mean <= 0:
            return None
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        cv_pct = (math.sqrt(variance) / mean) * 100.0
        # Bell-shaped preference: ~3–8% CV is "moderate"
        optimal = 5.5
        spread = 12.0
        raw = 100.0 - min(100.0, abs(cv_pct - optimal) / spread * 100.0)
        return round(_clamp_score(raw), 1)

    def calculate_price_change(
        self, item_name: str, hours: int | None = None
    ) -> float | None:
        """Percent change from earliest to latest price in window."""
        history = self.get_price_history(item_name, hours=hours)
        if len(history) < self.min_snapshots:
            return None
        prices = self._prices_from_history(history)
        if len(prices) < 2:
            return None
        first, last = prices[0], prices[-1]
        if first <= 0:
            return None
        return round(((last - first) / first) * 100.0, 2)

    def calculate_liquidity_score(self, item_name: str) -> float | None:
        """0–100 from average reported volume in lookback window."""
        history = self.get_price_history(item_name)
        if len(history) < self.min_snapshots:
            return None
        volumes = self._volumes_from_history(history)
        if not volumes:
            return None
        avg_vol = sum(volumes) / len(volumes)
        if avg_vol >= _LIQUIDITY_HIGH_VOL:
            return 100.0
        if avg_vol >= _LIQUIDITY_MED_VOL:
            return _clamp_score(50.0 + (avg_vol - _LIQUIDITY_MED_VOL) / (_LIQUIDITY_HIGH_VOL - _LIQUIDITY_MED_VOL) * 50.0)
        return _clamp_score(avg_vol / _LIQUIDITY_MED_VOL * 50.0)

    def calculate_momentum_score(self, item_name: str) -> float | None:
        """0–100 from recent vs older half-window price trend."""
        history = self.get_price_history(item_name)
        if len(history) < self.min_snapshots:
            return None
        prices = self._prices_from_history(history)
        mid = len(prices) // 2
        if mid < 1:
            return None
        older = prices[:mid]
        recent = prices[mid:]
        old_avg = sum(older) / len(older)
        new_avg = sum(recent) / len(recent)
        if old_avg <= 0:
            return None
        change_pct = ((new_avg - old_avg) / old_avg) * 100.0
        return round(_clamp_score(50.0 + change_pct * 2.5), 1)

    def _spread_stability_score(self, prices: list[float]) -> float:
        if len(prices) < 2:
            return 0.0
        mean = sum(prices) / len(prices)
        if mean <= 0:
            return 0.0
        price_range = max(prices) - min(prices)
        range_pct = (price_range / mean) * 100.0
        return _clamp_score(100.0 - min(100.0, range_pct * 4.0))

    def _price_movement_score(self, change_pct: float | None) -> float:
        if change_pct is None:
            return 0.0
        return _clamp_score(50.0 + change_pct * 2.0)

    def calculate_profit_score(self, item_name: str) -> dict | None:
        """Combined 0–100 profitability score with component breakdown."""
        if not self._has_sufficient_data(item_name):
            return None

        change_pct = self.calculate_price_change(item_name)
        liquidity = self.calculate_liquidity_score(item_name)
        volatility = self.calculate_volatility(item_name)
        momentum = self.calculate_momentum_score(item_name)

        if None in (liquidity, volatility, momentum):
            return None

        history = self.get_price_history(item_name)
        prices = self._prices_from_history(history)
        spread_stability = self._spread_stability_score(prices)
        price_movement = self._price_movement_score(change_pct)

        profit = (
            price_movement * 0.30
            + liquidity * 0.25
            + volatility * 0.20
            + spread_stability * 0.15
            + momentum * 0.10
        )
        profit = round(_clamp_score(profit), 1)

        momentum_pct = change_pct if change_pct is not None else 0.0
        recent_half = prices[len(prices) // 2 :] if len(prices) >= 2 else prices
        older_half = prices[: len(prices) // 2] if len(prices) >= 2 else prices
        if older_half and recent_half:
            oa = sum(older_half) / len(older_half)
            na = sum(recent_half) / len(recent_half)
            if oa > 0:
                momentum_pct = round(((na - oa) / oa) * 100.0, 1)

        return {
            "item_name": item_name,
            "profit_score": profit,
            "price_change_pct": change_pct,
            "momentum_pct": momentum_pct,
            "momentum_score": momentum,
            "liquidity_score": liquidity,
            "volatility_score": volatility,
            "spread_stability_score": round(spread_stability, 1),
            "liquidity_label": _label_from_score(liquidity, "High", "Medium", "Low"),
            "volatility_label": _label_from_score(volatility, "Moderate", "Low", "High"),
        }

    def _eligible_item_names(self) -> list[str]:
        conn = self._connect()
        if conn is None:
            return []
        try:
            rows = conn.execute(
                """
                SELECT item_name
                FROM price_history
                WHERE timestamp >= datetime('now', ?)
                GROUP BY item_name
                HAVING COUNT(*) >= ?
                ORDER BY COUNT(*) DESC
                LIMIT ?
                """,
                (
                    self._lookback_param(),
                    self.min_snapshots,
                    _MAX_CANDIDATES,
                ),
            ).fetchall()
            return [r["item_name"] for r in rows]
        except Exception as exc:
            log.error("eligible items query failed: %s", exc)
            return []
        finally:
            conn.close()

    def get_top_opportunities(
        self, limit: int = 10, min_score: float = 0.0
    ) -> list[dict]:
        """Rank items by profit score; ignores low-history and below min_score."""
        candidates = self._eligible_item_names()
        if not candidates:
            return []

        scored: list[dict] = []
        for name in candidates:
            try:
                row = self.calculate_profit_score(name)
                if row is not None and row["profit_score"] >= min_score:
                    scored.append(row)
            except Exception as exc:
                log.debug("profit score skipped for %s: %s", name, exc)

        scored.sort(key=lambda x: x["profit_score"], reverse=True)
        return scored[:limit]

    @staticmethod
    def format_opportunity_log(row: dict) -> str:
        sign = "+" if row.get("momentum_pct", 0) >= 0 else ""
        return (
            f"{row['item_name']}\n"
            f"Profit Score: {row['profit_score']:.0f}\n"
            f"Momentum: {sign}{row.get('momentum_pct', 0):.0f}%\n"
            f"Liquidity: {row.get('liquidity_label', 'n/a')}\n"
            f"Volatility: {row.get('volatility_label', 'n/a')}"
        )

    @staticmethod
    def format_telegram_alert(row: dict) -> str:
        sign = "+" if row.get("momentum_pct", 0) >= 0 else ""
        return (
            "📈 <b>Market opportunity</b>\n\n"
            f"<b>{row['item_name']}</b>\n"
            f"Profit score: <b>{row['profit_score']:.0f}</b>\n"
            f"Momentum: {sign}{row.get('momentum_pct', 0):.1f}%\n"
            f"Liquidity: {row.get('liquidity_label', 'n/a')}\n"
            f"Volatility: {row.get('volatility_label', 'n/a')}"
        )


def run_cycle_analytics() -> None:
    """Log top opportunities and optionally alert via Telegram (never raises)."""
    try:
        analytics = MarketAnalytics()
        top = analytics.get_top_opportunities(limit=10)
        if not top:
            log.debug("Analytics: no scored opportunities this cycle")
            return

        log.info("--- Top profitable items (analytics) ---")
        for row in top:
            log.info("\n%s", MarketAnalytics.format_opportunity_log(row))

        _maybe_telegram_alerts(top)
    except Exception as exc:
        log.error("Analytics cycle failed (monitor continues): %s", exc)


def _maybe_telegram_alerts(opportunities: list[dict]) -> None:
    from app.alert_store import record_alert, should_send_signal_alert
    from app.notifier import is_telegram_configured, send_raw_message

    if not is_telegram_configured():
        return

    for row in opportunities:
        if row["profit_score"] < MIN_PROFIT_SCORE_ALERT:
            continue
        item_name = row["item_name"]
        signal = "PROFIT_SCORE"
        try:
            if not should_send_signal_alert(item_name, signal):
                continue
            text = MarketAnalytics.format_telegram_alert(row)
            if send_raw_message(text):
                record_alert(item_name, signal)
                log.info(
                    "Telegram profit-score alert sent for %s (score=%.0f)",
                    item_name,
                    row["profit_score"],
                )
        except Exception as exc:
            log.error(
                "Profit-score Telegram alert failed for %s (monitor continues): %s",
                item_name,
                exc,
            )
