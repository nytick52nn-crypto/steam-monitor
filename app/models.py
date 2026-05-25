from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Integer, String

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)

    item_name = Column(String, index=True)
    hash_name = Column(String, index=True)

    price = Column(Float)
    volume = Column(Integer)

    created_at = Column(DateTime, default=utc_now)


class AlertSent(Base):
    __tablename__ = "alert_sent"

    id = Column(Integer, primary_key=True)
    item_name = Column(String, index=True)
    signal = Column(String, index=True)
    sent_at = Column(DateTime, default=utc_now, index=True)


class Wallet(Base):
    """Singleton virtual wallet (row id=1)."""

    __tablename__ = "wallet"

    id = Column(Integer, primary_key=True)
    balance = Column(Float, nullable=False, default=0.0)
    starting_balance = Column(Float, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)


class OpenPosition(Base):
    """Paper trade position with BUY entry and SELL exit tracking."""

    __tablename__ = "open_positions"

    id = Column(Integer, primary_key=True)
    item_name = Column(String, index=True)
    hash_name = Column(String)
    entry_price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False, default=1.0)
    cost = Column(Float, nullable=False)
    status = Column(String, index=True, default="open")
    signal = Column(String, default="BUY")
    opened_at = Column(DateTime, default=utc_now, index=True)
    exit_price = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    pnl_rub = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
