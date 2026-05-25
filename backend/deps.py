"""FastAPI dependencies — reuse existing app modules."""

from __future__ import annotations

from functools import lru_cache

from app.analytics import MarketAnalytics
from app.risk_manager import RiskManager


@lru_cache
def get_analytics() -> MarketAnalytics:
    return MarketAnalytics()


@lru_cache
def get_risk_manager() -> RiskManager:
    return RiskManager()
