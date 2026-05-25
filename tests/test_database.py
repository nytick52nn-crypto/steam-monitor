"""Tests for app.database — engine, sessions, and model persistence."""

from __future__ import annotations

import pytest
from sqlalchemy import inspect

import app.config as app_config
from app.database import Base, engine
from app.models import AlertSent, OpenPosition, PriceHistory, Wallet


@pytest.mark.integration
def test_config_database_url_from_env(config):
    """DATABASE_URL is loaded from real .env / defaults (no override)."""
    assert config.DATABASE_URL
    assert "sqlite" in config.DATABASE_URL.lower()


class TestIsolatedDatabase:
    def test_tables_created(self, isolated_db):
        tables = inspect(isolated_db.bind).get_table_names()
        for name in ("price_history", "alert_sent", "wallet", "open_positions"):
            assert name in tables

    def test_session_local_factory(self, isolated_db):
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            assert session.bind is isolated_db.bind
        finally:
            session.close()

    def test_price_history_roundtrip(self, isolated_db):
        row = PriceHistory(
            item_name="DB Test",
            hash_name="DB%20Test",
            price=42.5,
            volume=17,
        )
        isolated_db.add(row)
        isolated_db.commit()
        isolated_db.expire_all()
        loaded = (
            isolated_db.query(PriceHistory)
            .filter_by(item_name="DB Test")
            .one()
        )
        assert loaded.price == 42.5
        assert loaded.volume == 17

    def test_alert_sent_and_wallet_models(self, isolated_db):
        isolated_db.add(
            AlertSent(item_name="Item", signal="BUY"),
        )
        isolated_db.add(
            Wallet(id=1, balance=5000.0, starting_balance=5000.0),
        )
        isolated_db.commit()
        assert isolated_db.query(AlertSent).count() == 1
        assert isolated_db.query(Wallet).one().balance == 5000.0

    def test_open_position_defaults(self, isolated_db):
        pos = OpenPosition(
            item_name="Case",
            hash_name="Case",
            entry_price=10.0,
            cost=10.0,
        )
        isolated_db.add(pos)
        isolated_db.commit()
        loaded = isolated_db.query(OpenPosition).one()
        assert loaded.status == "open"
        assert loaded.quantity == 1.0


class TestProductionEngine:
    def test_production_engine_connects(self, config):
        """Smoke-test the real engine from config (read-only metadata)."""
        with engine.connect() as conn:
            assert conn is not None
        assert str(engine.url).startswith("sqlite")
