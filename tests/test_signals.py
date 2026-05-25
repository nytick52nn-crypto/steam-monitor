"""Tests for app.signals — history loading and evaluate_and_notify."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.models import PriceHistory
from app.signals import evaluate_and_notify, load_price_history


def _make_ohlc_prices(n: int, base: float = 100.0) -> list[float]:
    """Prices with enough variation for indicators after add_indicators."""
    return [base + (i % 7) * 2.5 - (i % 3) * 1.2 for i in range(n)]


class TestLoadPriceHistory:
    def test_load_price_history_empty(self, isolated_db):
        df = load_price_history("Unknown", isolated_db)
        assert df.empty

    def test_load_price_history_ordered(self, isolated_db, price_rows_factory):
        item = "Signal Test Item"
        prices = _make_ohlc_prices(25, 80.0)
        price_rows_factory(item, prices)
        df = load_price_history(item, isolated_db)
        assert len(df) == 25
        assert list(df.columns) == ["created_at", "price", "volume"]
        assert df["price"].iloc[-1] == prices[-1]


class TestEvaluateAndNotify:
    def test_insufficient_history_returns_none(self, isolated_db):
        isolated_db.add(
            PriceHistory(
                item_name="Short",
                hash_name="Short",
                price=50.0,
                volume=10,
            )
        )
        isolated_db.commit()
        with patch("app.signals.MIN_HISTORY_FOR_SIGNAL", 20):
            result = evaluate_and_notify("Short", 50.0, 10)
        assert result is None

    def test_evaluate_hold_with_enough_history(
        self, isolated_db, price_rows_factory, config
    ):
        item = "Hold Item"
        price_rows_factory(item, _make_ohlc_prices(30, 120.0))
        hold_result = {
            "signal": "HOLD",
            "reasoning": ["No setup"],
            "estimated_profit_pct": 0.0,
            "confidence": 0.2,
        }
        with (
            patch(
                "app.signals.get_detailed_trade_signal",
                return_value=hold_result,
            ),
            patch("app.signals.should_send_signal_alert", return_value=True),
            patch("app.signals.is_telegram_configured", return_value=False),
        ):
            result = evaluate_and_notify(item, 120.0, 100)
        assert result == "HOLD"

    def test_evaluate_buy_skips_duplicate_signal(
        self, isolated_db, price_rows_factory
    ):
        item = "Buy Item"
        price_rows_factory(item, _make_ohlc_prices(30, 90.0))
        buy_result = {
            "signal": "BUY",
            "reasoning": ["Oversold"],
            "estimated_profit_pct": 18.0,
            "confidence": 0.85,
        }
        with (
            patch(
                "app.signals.get_detailed_trade_signal",
                return_value=buy_result,
            ),
            patch("app.signals.should_send_signal_alert", return_value=True),
            patch("app.signals.is_telegram_configured", return_value=False),
            patch("app.signals.execute_paper_buy", return_value=None),
            patch(
                "app.signals._risk_manager.is_trade_allowed",
                return_value=(True, "ok"),
            ),
        ):
            first = evaluate_and_notify(item, 90.0, 150)
            second = evaluate_and_notify(item, 91.0, 150)
        assert first == "BUY"
        assert second == "BUY"

    def test_evaluate_buy_triggers_paper_when_enabled(
        self, isolated_db, price_rows_factory
    ):
        item = "Fresh Buy"
        price_rows_factory(item, _make_ohlc_prices(30, 75.0))
        buy_result = {
            "signal": "BUY",
            "reasoning": ["Setup"],
            "estimated_profit_pct": 20.0,
            "confidence": 0.9,
        }
        mock_position = MagicMock()
        mock_position.id = 99

        with (
            patch(
                "app.signals.get_detailed_trade_signal",
                return_value=buy_result,
            ),
            patch("app.signals.should_send_signal_alert", return_value=True),
            patch("app.signals.is_telegram_configured", return_value=False),
            patch("app.signals.execute_paper_buy", return_value=mock_position) as mock_buy,
            patch.dict("app.signals._last_evaluated", {}, clear=True),
            patch(
                "app.signals._risk_manager.is_trade_allowed",
                return_value=(True, "ok"),
            ),
            patch(
                "app.signals._risk_manager.calculate_position_size",
                return_value=750.0,
            ),
            patch("app.wallet.get_balance", return_value=10_000.0),
            patch("app.paper_trading.get_open_positions", return_value=[]),
        ):
            result = evaluate_and_notify(item, 75.0, 200)
        assert result == "BUY"
        mock_buy.assert_called_once()
        assert mock_buy.call_args[0][0] == item
        assert mock_buy.call_args[0][1] == 75.0
