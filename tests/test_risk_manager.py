"""Tests for app.risk_manager — sizing, heat limits, and trade gates."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.risk_manager import RiskManager, _position_cost


class TestRiskManagerBasics:
    def test_get_max_risk_per_trade_default(self, monkeypatch):
        monkeypatch.setattr("app.risk_manager.MAX_RISK_PER_TRADE", 0.015)
        rm = RiskManager()
        assert rm.get_max_risk_per_trade() == pytest.approx(0.015)

    def test_calculate_position_size_scales_with_score(self):
        rm = RiskManager()
        low = rm.calculate_position_size(10_000, 30, 50, "Item")
        high = rm.calculate_position_size(10_000, 90, 50, "Item")
        assert high > low > 0

    def test_higher_volatility_reduces_size(self):
        rm = RiskManager()
        calm = rm.calculate_position_size(10_000, 80, 20, "Item")
        volatile = rm.calculate_position_size(10_000, 80, 80, "Item")
        assert calm > volatile

    def test_calculate_position_size_safe_with_bad_input(self):
        rm = RiskManager()
        assert rm.calculate_position_size(0, 50, 50) == 0.0
        assert rm.calculate_position_size(-100, 50, 50) == 0.0
        assert rm.calculate_position_size(10_000, None, None) >= 0

    def test_calculate_dynamic_stop_loss(self):
        rm = RiskManager()
        stop_low = rm.calculate_dynamic_stop_loss(100.0, 20)
        stop_high = rm.calculate_dynamic_stop_loss(100.0, 80)
        assert stop_low < 100.0
        assert stop_high < stop_low

    def test_volatility_risk_from_prices(self):
        flat = [100.0] * 10
        wavy = [100 + (i % 3) * 15 for i in range(10)]
        assert RiskManager.volatility_risk_from_prices(flat) < RiskManager.volatility_risk_from_prices(wavy)


class TestPortfolioHeat:
    def test_check_portfolio_heat_within_limit(self):
        rm = RiskManager()
        positions = [{"cost": 1000.0}, {"cost": 500.0}]
        assert rm.check_portfolio_heat(positions, 10_000) is True

    def test_check_portfolio_heat_exceeded(self, monkeypatch):
        monkeypatch.setattr("app.risk_manager.MAX_PORTFOLIO_HEAT", 0.25)
        rm = RiskManager()
        positions = [{"cost": 2000.0}, {"cost": 1000.0}]
        assert rm.check_portfolio_heat(positions, 10_000) is False

    def test_portfolio_heat_empty_positions(self):
        rm = RiskManager()
        assert rm.check_portfolio_heat([], 10_000) is True
        assert rm.check_portfolio_heat(None, 10_000) is True

    def test_position_cost_fallback(self):
        assert _position_cost({"entry_price": 50, "quantity": 2}) == 100.0
        assert _position_cost({"cost": 75.5}) == 75.5
        assert _position_cost({}) == 0.0


class TestIsTradeAllowed:
    def test_blocked_low_profit_score(self, monkeypatch):
        monkeypatch.setattr("app.risk_manager.MIN_PROFIT_SCORE_ALERT", 70.0)
        rm = RiskManager()
        allowed, reason = rm.is_trade_allowed(
            "Test", 50.0, 40.0, 10_000, []
        )
        assert allowed is False
        assert "Profit score" in reason

    def test_allowed_high_score_empty_book(self, monkeypatch):
        monkeypatch.setattr("app.risk_manager.MIN_PROFIT_SCORE_ALERT", 70.0)
        rm = RiskManager()
        allowed, reason = rm.is_trade_allowed(
            "Test", 85.0, 40.0, 10_000, []
        )
        assert allowed is True
        assert reason == "Trade allowed"

    def test_skips_profit_score_when_negative(self, monkeypatch):
        monkeypatch.setattr("app.risk_manager.MIN_PROFIT_SCORE_ALERT", 70.0)
        rm = RiskManager()
        allowed, _ = rm.is_trade_allowed("Test", -1.0, 40.0, 10_000, [])
        assert allowed is True

    def test_get_item_risk_metrics_never_raises(self):
        rm = RiskManager()
        with patch(
            "app.analytics.MarketAnalytics.calculate_profit_score",
            side_effect=RuntimeError("db"),
        ):
            metrics = rm.get_item_risk_metrics("Ghost Item")
        assert metrics["item_name"] == "Ghost Item"
        assert metrics["profit_score"] == -1.0


class TestBacktester:
    def test_backtester_short_history_returns_empty(self):
        from app.backtester import Backtester

        bt = Backtester()
        result = bt.run("Item", [100.0] * 5)
        assert result.trade_count == 0
        assert result.ending_balance == result.starting_balance

    def test_backtester_never_raises_on_bad_prices(self):
        from app.backtester import Backtester

        bt = Backtester(min_history=10)
        result = bt.run("Item", [], volumes=None)
        assert result.trade_count == 0
