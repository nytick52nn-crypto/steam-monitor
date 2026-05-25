"""Shared pytest fixtures — config loads from the project root .env via app.config."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.config as app_config
from app.database import Base
from app.models import PriceHistory


@pytest.fixture(scope="session")
def config():
    """Real settings loaded from the existing .env (via config.py)."""
    assert app_config.DATA_DIR is not None
    return app_config


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    """In-memory SQLAlchemy DB; patches SessionLocal in database, monitor, and signals."""
    db_file = tmp_path / "test_steam_cards.db"
    url = f"sqlite:///{db_file.as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    monkeypatch.setattr("app.database.engine", engine)
    monkeypatch.setattr("app.database.SessionLocal", session_factory)
    monkeypatch.setattr("app.monitor.SessionLocal", session_factory)
    monkeypatch.setattr("app.signals.SessionLocal", session_factory)

    session = session_factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def price_history_db(tmp_path, monkeypatch):
    """Temporary price_history.db for MarketAnalytics (does not touch production file)."""
    db_path = tmp_path / "price_history_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            price REAL NOT NULL,
            volume INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX idx_price_history_item_ts ON price_history (item_name, timestamp)"
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("app.analytics.PRICE_HISTORY_DB", str(db_path))
    return db_path


def seed_price_snapshots(
    db_path: Path,
    item_name: str,
    prices: list[float],
    volumes: list[int] | None = None,
    *,
    minutes_apart: int = 30,
) -> None:
    """Insert snapshots spread across the last N*minutes_apart minutes (within 24h lookback)."""
    if volumes is None:
        volumes = [50] * len(prices)
    conn = sqlite3.connect(str(db_path))
    try:
        now = datetime.now()
        for i, (price, vol) in enumerate(zip(prices, volumes)):
            ts = now - timedelta(minutes=minutes_apart * (len(prices) - 1 - i))
            conn.execute(
                """
                INSERT INTO price_history (item_name, price, volume, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (item_name, price, vol, ts.strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def seeded_analytics_db(price_history_db):
    """Analytics DB with one item that meets MIN_HISTORY_SNAPSHOTS."""
    item = "Test Case | Analytics"
    base = 100.0
    prices = [base + (i % 5) * 0.8 for i in range(25)]
    volumes = [90] * 25
    seed_price_snapshots(price_history_db, item, prices, volumes)
    return price_history_db, item


@pytest.fixture
def price_rows_factory(isolated_db):
    """Factory to insert PriceHistory rows into the isolated main DB."""

    def _add(item_name: str, prices: list[float], volumes: list[int] | None = None):
        if volumes is None:
            volumes = [100] * len(prices)
        for price, vol in zip(prices, volumes):
            isolated_db.add(
                PriceHistory(
                    item_name=item_name,
                    hash_name=item_name,
                    price=price,
                    volume=vol,
                )
            )
        isolated_db.commit()

    return _add
