"""Risk management: position sizing, portfolio heat, and trade gates."""

from __future__ import annotations

import math
from typing import Any

from app.config import (
    MAX_PORTFOLIO_HEAT,
    MAX_RISK_PER_TRADE,
    MIN_PROFIT_SCORE_ALERT,
    POSITION_SCALING_FACTOR,
)
from app.logger import setup_logging

log = setup_logging("risk_manager")

_DEFAULT_VOLATILITY_RISK = 50.0
_BASE_STOP_LOSS_PCT = 8.0
_MIN_POSITION_RUB = 1.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        f = float(value)
        if not math.isfinite(f):
            return default
        return f
    except (TypeError, ValueError):
        return default


def _normalize_profit_score(profit_score: float) -> float:
    return max(0.0, min(100.0, _safe_float(profit_score, 0.0)))


def _normalize_volatility_risk(volatility: float | None) -> float:
    """Map volatility to 0–100 risk scale; higher = more volatile / smaller size."""
    v = _safe_float(volatility, _DEFAULT_VOLATILITY_RISK)
    if v <= 0:
        return _DEFAULT_VOLATILITY_RISK
    if v <= 100:
        return max(0.0, min(100.0, v))
    return min(100.0, v)


def _position_cost(pos: dict) -> float:
    cost = pos.get("cost")
    if cost is not None:
        return max(0.0, _safe_float(cost, 0.0))
    entry = _safe_float(pos.get("entry_price"), 0.0)
    qty = _safe_float(pos.get("quantity"), 1.0)
    return max(0.0, entry * qty)


class RiskManager:
    """Position sizing, portfolio heat limits, and trade approval gates."""

    def get_max_risk_per_trade(self) -> float:
        return max(0.0, _safe_float(MAX_RISK_PER_TRADE, 0.015))

    def portfolio_heat_ratio(
        self, open_positions: list | None, account_balance: float
    ) -> float:
        if not open_positions or account_balance <= 0:
            return 0.0
        total = sum(_position_cost(p) for p in open_positions if isinstance(p, dict))
        return total / account_balance

    def check_portfolio_heat(
        self, open_positions: list | None, account_balance: float | None = None
    ) -> bool:
        """Return True when total open exposure is within MAX_PORTFOLIO_HEAT."""
        balance = _safe_float(account_balance, 0.0)
        if balance <= 0:
            log.debug("Portfolio heat check: no balance, allowing")
            return True
        heat = self.portfolio_heat_ratio(open_positions, balance)
        limit = max(0.0, _safe_float(MAX_PORTFOLIO_HEAT, 0.30))
        ok = heat <= limit
        if not ok:
            log.info(
                "Portfolio heat %.1f%% exceeds limit %.1f%%",
                heat * 100,
                limit * 100,
            )
        return ok

    def calculate_position_size(
        self,
        account_balance: float,
        profit_score: float,
        volatility: float,
        item_name: str = "",
    ) -> float:
        """
        Risk-based position size in RUB.

        Higher profit_score increases size; higher volatility decreases size.
        Capped by per-trade risk budget and remaining portfolio heat headroom.
        """
        balance = _safe_float(account_balance, 0.0)
        if balance <= 0:
            log.debug("Position size 0 for %s: zero balance", item_name or "?")
            return 0.0

        score = _normalize_profit_score(profit_score)
        vol_risk = _normalize_volatility_risk(volatility)

        risk_budget = balance * self.get_max_risk_per_trade()
        profit_factor = 0.5 + (score / 100.0) * 0.5
        vol_factor = max(0.25, 1.0 - (vol_risk / 100.0) * 0.75)
        scale = max(0.0, _safe_float(POSITION_SCALING_FACTOR, 1.0))

        raw_size = risk_budget * profit_factor * vol_factor * scale
        size = max(0.0, round(raw_size, 2))

        if size < _MIN_POSITION_RUB:
            log.debug(
                "Position size below minimum for %s: %.2f (score=%.0f vol=%.0f)",
                item_name or "?",
                size,
                score,
                vol_risk,
            )
            return 0.0

        log.debug(
            "Position size %s: %.2f RUB (balance=%.2f score=%.0f vol_risk=%.0f)",
            item_name or "?",
            size,
            balance,
            score,
            vol_risk,
        )
        return size

    def calculate_dynamic_stop_loss(
        self, entry_price: float, volatility: float
    ) -> float:
        """Stop price below entry; wider when volatility risk is higher."""
        entry = _safe_float(entry_price, 0.0)
        if entry <= 0:
            return 0.0

        vol_risk = _normalize_volatility_risk(volatility)
        stop_pct = _BASE_STOP_LOSS_PCT * (1.0 + vol_risk / 100.0)
        stop_pct = min(stop_pct, 25.0)
        stop_price = entry * (1.0 - stop_pct / 100.0)
        return max(0.0, round(stop_price, 2))

    def is_trade_allowed(
        self,
        item_name: str,
        profit_score: float,
        volatility: float,
        account_balance: float,
        open_positions: list | None,
    ) -> tuple[bool, str]:
        """Return (allowed, reason). Safe with missing or partial data."""
        name = (item_name or "").strip() or "unknown"
        balance = _safe_float(account_balance, 0.0)

        if balance <= 0:
            return False, "Account balance is zero or invalid"

        score = _safe_float(profit_score, -1.0)
        min_score = _safe_float(MIN_PROFIT_SCORE_ALERT, 70.0)
        if score >= 0 and score < min_score:
            return (
                False,
                f"Profit score {score:.0f} below minimum {min_score:.0f}",
            )

        if not self.check_portfolio_heat(open_positions, balance):
            heat = self.portfolio_heat_ratio(open_positions, balance)
            return (
                False,
                f"Portfolio heat {heat * 100:.1f}% exceeds "
                f"{MAX_PORTFOLIO_HEAT * 100:.0f}% limit",
            )

        size = self.calculate_position_size(
            balance, profit_score, volatility, name
        )
        if size <= 0:
            return False, "Calculated position size is zero"

        heat_after = self.portfolio_heat_ratio(open_positions, balance)
        limit = max(0.0, _safe_float(MAX_PORTFOLIO_HEAT, 0.30))
        if heat_after + (size / balance) > limit:
            return False, "New position would exceed portfolio heat limit"

        return True, "Trade allowed"

    @staticmethod
    def volatility_risk_from_prices(prices: list[float]) -> float:
        """Coefficient-of-variation % mapped to 0–100 risk (higher = more volatile)."""
        if not prices or len(prices) < 2:
            return _DEFAULT_VOLATILITY_RISK
        clean = [_safe_float(p, 0.0) for p in prices if _safe_float(p, 0.0) > 0]
        if len(clean) < 2:
            return _DEFAULT_VOLATILITY_RISK
        mean = sum(clean) / len(clean)
        if mean <= 0:
            return _DEFAULT_VOLATILITY_RISK
        variance = sum((p - mean) ** 2 for p in clean) / len(clean)
        cv_pct = (math.sqrt(variance) / mean) * 100.0
        return max(0.0, min(100.0, cv_pct * 10.0))

    def get_item_risk_metrics(self, item_name: str) -> dict:
        """
        Load profit_score and volatility risk from MarketAnalytics (never raises).
        """
        result = {
            "item_name": item_name,
            "profit_score": -1.0,
            "volatility_risk": _DEFAULT_VOLATILITY_RISK,
            "has_analytics": False,
        }
        if not item_name:
            return result
        try:
            from app.analytics import MarketAnalytics

            analytics = MarketAnalytics()
            row = analytics.calculate_profit_score(item_name)
            if row:
                result["profit_score"] = _safe_float(row.get("profit_score"), -1.0)
                result["has_analytics"] = True
            history = analytics.get_price_history(item_name)
            prices = [
                h["price"]
                for h in history
                if h.get("price") is not None
            ]
            result["volatility_risk"] = self.volatility_risk_from_prices(prices)
        except Exception as exc:
            log.debug("Risk metrics unavailable for %s: %s", item_name, exc)
        return result
