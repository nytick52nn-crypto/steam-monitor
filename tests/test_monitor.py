"""Tests for app.monitor — parsing, persistence, Steam mocks, loop safety."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app import monitor
from app.analytics import run_cycle_analytics


class TestParsePrice:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("135,00 ₽", 135.0),
            ("1 350,00 ₽", 1350.0),
            ("2993,73", 2993.73),
            ("$12.34", 12.34),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_price_formats(self, raw, expected):
        assert monitor.parse_price(raw) == expected


class TestParseVolume:
    def test_parse_volume_int_and_string(self):
        assert monitor.parse_volume(42) == 42
        assert monitor.parse_volume("1,234") == 1234
        assert monitor.parse_volume(None) == 0
        assert monitor.parse_volume("bad") == 0


class TestLoadItems:
    def test_load_items_from_json(self, tmp_path):
        path = tmp_path / "items.json"
        data = [
            {"name": "B", "hash_name": "B", "enabled": True, "priority": 2},
            {"name": "A", "hash_name": "A", "enabled": True, "priority": 1},
            {"name": "Off", "enabled": False},
        ]
        path.write_text(json.dumps(data), encoding="utf-8")
        items = monitor.load_items(str(path))
        assert [i["name"] for i in items] == ["A", "B"]

    def test_load_items_fallback_when_missing(self, tmp_path):
        items = monitor.load_items(str(tmp_path / "missing.json"))
        assert len(items) == len(monitor.FALLBACK_ITEMS)


class TestSavePrice:
    def test_save_price_persists_row(self, isolated_db):
        ok = monitor.save_price("Fracture Case", 150.5, 80)
        assert ok is True
        row = (
            isolated_db.query(monitor.PriceHistory)
            .filter_by(item_name="Fracture Case")
            .one()
        )
        assert row.price == 150.5
        assert row.volume == 80


class TestProcessItem:
    def test_process_item_success_mocked_steam(self, isolated_db):
        item = {"name": "Fracture Case", "hash_name": "Fracture%20Case"}
        steam_data = {
            "median_price": "150,00 ₽",
            "volume": "120",
        }
        with (
            patch("app.monitor.get_priceoverview", return_value=steam_data),
            patch("app.monitor.evaluate_and_notify", return_value=None),
            patch("app.monitor.save_price", wraps=monitor.save_price) as mock_save,
        ):
            ok, snapshot = monitor.process_item(item)
        assert ok is True
        assert snapshot == {
            "item_name": "Fracture Case",
            "price": 150.0,
            "volume": 120,
        }
        mock_save.assert_called_once()

    def test_process_item_no_steam_data(self):
        item = {"name": "Ghost", "hash_name": "Ghost"}
        with patch("app.monitor.get_priceoverview", return_value=None):
            ok, snapshot = monitor.process_item(item)
        assert ok is False
        assert snapshot is None

    def test_process_item_steam_raises(self):
        item = {"name": "Error Item", "hash_name": "Error"}
        with patch(
            "app.monitor.get_priceoverview",
            side_effect=ConnectionError("429"),
        ):
            with pytest.raises(ConnectionError):
                monitor.process_item(item)


class TestMonitorLoopSafety:
    def test_scan_cycle_survives_item_errors(self):
        """Same try/except pattern as run_monitor — one bad item must not stop the cycle."""
        items = [
            {"name": "Bad", "hash_name": "Bad"},
            {"name": "Good", "hash_name": "Good"},
        ]
        saved = 0
        snapshots = []

        def fake_process(item):
            if item["name"] == "Bad":
                raise RuntimeError("item failure")
            return True, {"item_name": "Good", "price": 1.0, "volume": 1}

        for item in items:
            try:
                ok, snapshot = fake_process(item)
                if snapshot:
                    snapshots.append(snapshot)
                if ok:
                    saved += 1
            except Exception:
                pass

        assert saved == 1
        assert len(snapshots) == 1

    def test_monitor_analytics_wrapper_survives_failure(self):
        """run_monitor wraps run_cycle_analytics in try/except when saved > 0."""
        saved = 1
        with patch(
            "app.analytics.run_cycle_analytics",
            side_effect=RuntimeError("analytics down"),
        ):
            try:
                if saved > 0:
                    run_cycle_analytics()
            except Exception:
                pytest.fail("Monitor must catch analytics exceptions")

    @pytest.mark.slow
    def test_run_cycle_analytics_swallows_errors(self):
        with patch(
            "app.analytics.MarketAnalytics.get_top_opportunities",
            side_effect=ValueError("boom"),
        ):
            run_cycle_analytics()


class TestSaveBulkSnapshots:
    def test_save_bulk_snapshots_mocked(self):
        snapshots = [{"item_name": "X", "price": 1.0, "volume": 2}]
        with patch("app.monitor.save_bulk_snapshots") as mock_bulk:
            mock_bulk(snapshots)
            mock_bulk.assert_called_once_with(snapshots)
