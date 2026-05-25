"""Tests for app.analytics — scoring, rankings, and cycle safety."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.analytics import (
    MarketAnalytics,
    _clamp_score,
    _label_from_score,
    run_cycle_analytics,
)
from tests.conftest import seed_price_snapshots


class TestScoreHelpers:
    def test_clamp_score_bounds(self):
        assert _clamp_score(-10) == 0.0
        assert _clamp_score(150) == 100.0
        assert _clamp_score(42.5) == 42.5

    def test_label_from_score(self):
        assert _label_from_score(70, "High", "Medium", "Low") == "High"
        assert _label_from_score(40, "High", "Medium", "Low") == "Medium"
        assert _label_from_score(10, "High", "Medium", "Low") == "Low"


class TestMarketAnalytics:
    def test_missing_db_returns_empty_history(self, tmp_path, monkeypatch):
        missing = tmp_path / "nonexistent.db"
        monkeypatch.setattr("app.analytics.PRICE_HISTORY_DB", str(missing))
        analytics = MarketAnalytics(min_snapshots=5)
        assert analytics.get_price_history("Any") == []

    def test_insufficient_snapshots_returns_none(self, price_history_db):
        seed_price_snapshots(
            price_history_db,
            "Sparse Item",
            [100.0, 101.0],
            minutes_apart=60,
        )
        analytics = MarketAnalytics(min_snapshots=20)
        assert analytics.calculate_volatility("Sparse Item") is None
        assert analytics.calculate_profit_score("Sparse Item") is None

    def test_calculate_price_change(self, seeded_analytics_db):
        db_path, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        change = analytics.calculate_price_change(item)
        assert change is not None
        assert isinstance(change, float)

    def test_calculate_volatility_moderate_range(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        vol = analytics.calculate_volatility(item)
        assert vol is not None
        assert 0 <= vol <= 100

    def test_calculate_liquidity_high_volume(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        liq = analytics.calculate_liquidity_score(item)
        assert liq == 100.0

    def test_calculate_momentum_score(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        mom = analytics.calculate_momentum_score(item)
        assert mom is not None
        assert 0 <= mom <= 100

    def test_calculate_profit_score_structure(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        row = analytics.calculate_profit_score(item)
        assert row is not None
        assert row["item_name"] == item
        assert 0 <= row["profit_score"] <= 100
        for key in (
            "liquidity_score",
            "volatility_score",
            "momentum_score",
            "spread_stability_score",
            "liquidity_label",
            "volatility_label",
        ):
            assert key in row

    def test_get_top_opportunities_sorted(self, price_history_db):
        seed_price_snapshots(
            price_history_db,
            "Item A",
            [100.0 + i for i in range(25)],
            [80] * 25,
        )
        seed_price_snapshots(
            price_history_db,
            "Item B",
            [200.0 - i * 0.5 for i in range(25)],
            [40] * 25,
        )
        analytics = MarketAnalytics(min_snapshots=20)
        top = analytics.get_top_opportunities(limit=5)
        assert len(top) >= 1
        scores = [r["profit_score"] for r in top]
        assert scores == sorted(scores, reverse=True)

    def test_format_helpers(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        row = analytics.calculate_profit_score(item)
        assert item in MarketAnalytics.format_opportunity_log(row)
        assert "Market opportunity" in MarketAnalytics.format_telegram_alert(row)

    def test_profit_score_uses_all_components(self, seeded_analytics_db):
        _, item = seeded_analytics_db
        analytics = MarketAnalytics(min_snapshots=20)
        history = [{"price": 100.0, "volume": 50}, {"price": 105.0, "volume": 50}]

        with (
            patch.object(analytics, "_has_sufficient_data", return_value=True),
            patch.object(analytics, "calculate_price_change", return_value=10.0),
            patch.object(analytics, "calculate_liquidity_score", return_value=80.0),
            patch.object(analytics, "calculate_volatility", return_value=60.0),
            patch.object(analytics, "calculate_momentum_score", return_value=70.0),
            patch.object(analytics, "get_price_history", return_value=history),
            patch.object(analytics, "_spread_stability_score", return_value=50.0),
        ):
            row = analytics.calculate_profit_score(item)

        price_movement = 70.0  # 50 + 10 * 2
        expected = round(
            price_movement * 0.30
            + 80.0 * 0.25
            + 60.0 * 0.20
            + 50.0 * 0.15
            + 70.0 * 0.10,
            1,
        )
        assert row is not None
        assert row["profit_score"] == expected

    def test_get_top_opportunities_respects_min_score(self, price_history_db):
        seed_price_snapshots(
            price_history_db,
            "High Score Item",
            [100.0 + i for i in range(25)],
            [90] * 25,
        )
        seed_price_snapshots(
            price_history_db,
            "Low Score Item",
            [200.0 - i * 2 for i in range(25)],
            [5] * 25,
        )
        analytics = MarketAnalytics(min_snapshots=20)
        all_ranked = analytics.get_top_opportunities(limit=10, min_score=0.0)
        assert len(all_ranked) >= 2
        high_row = next(
            r for r in all_ranked if r["item_name"] == "High Score Item"
        )
        low_row = next(r for r in all_ranked if r["item_name"] == "Low Score Item")
        threshold = (high_row["profit_score"] + low_row["profit_score"]) / 2
        filtered = analytics.get_top_opportunities(limit=10, min_score=threshold)
        names = {r["item_name"] for r in filtered}
        assert "High Score Item" in names
        assert "Low Score Item" not in names
        assert all(r["profit_score"] >= threshold for r in filtered)

    def test_analytics_respects_lookback_hours_from_config(
        self, price_history_db, monkeypatch
    ):
        monkeypatch.setattr("app.analytics.ANALYTICS_LOOKBACK_HOURS", 2)
        analytics = MarketAnalytics(lookback_hours=2, min_snapshots=5)
        seed_price_snapshots(
            price_history_db,
            "Recent Item",
            [100.0 + i * 0.5 for i in range(10)],
            minutes_apart=10,
        )
        old_ts = (
            datetime.now(timezone.utc) - timedelta(hours=48)
        ).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(str(price_history_db))
        try:
            for i in range(10):
                conn.execute(
                    """
                    INSERT INTO price_history (item_name, price, volume, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    ("Stale Item", 50.0 + i, 40, old_ts),
                )
            conn.commit()
        finally:
            conn.close()

        assert analytics._snapshot_count("Recent Item") >= 5
        assert analytics._snapshot_count("Stale Item") == 0
        assert analytics.get_price_history("Stale Item") == []


class TestRunCycleAnalytics:
    def test_run_cycle_analytics_never_raises_on_internal_error(self):
        with patch.object(
            MarketAnalytics,
            "get_top_opportunities",
            side_effect=RuntimeError("analytics broken"),
        ):
            run_cycle_analytics()

    def test_run_cycle_analytics_empty_top(self):
        with patch.object(MarketAnalytics, "get_top_opportunities", return_value=[]):
            run_cycle_analytics()
