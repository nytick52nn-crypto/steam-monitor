from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from app.analytics import MarketAnalytics
from app.config import (
    PRICE_HISTORY_DB,
    telegram_config_status,
)
from backend.deps import get_analytics
from backend.schemas.system import DashboardKPIs, HealthComponent, SystemHealthResponse
from backend.utils import get_last_scan_time, monitor_recently_active

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health", response_model=SystemHealthResponse)
def system_health(analytics: MarketAnalytics = Depends(get_analytics)) -> SystemHealthResponse:
    components: list[HealthComponent] = []
    statuses: list[str] = []

    db_path = Path(PRICE_HISTORY_DB)
    if db_path.is_file():
        components.append(
            HealthComponent(
                name="price_history_db",
                status="ok",
                detail=str(db_path),
            )
        )
        statuses.append("ok")
    else:
        components.append(
            HealthComponent(
                name="price_history_db",
                status="warn",
                detail="Not found — monitor may not have run yet",
            )
        )
        statuses.append("warn")

    tg = telegram_config_status()
    tg_status = "ok" if tg["ready"] else "warn"
    components.append(
        HealthComponent(
            name="telegram",
            status=tg_status,
            detail="; ".join(tg["issues"]) if tg["issues"] else "Configured",
        )
    )
    statuses.append(tg_status)

    monitor_ok = monitor_recently_active()
    components.append(
        HealthComponent(
            name="monitor",
            status="ok" if monitor_ok else "warn",
            detail="Active in last 30 min" if monitor_ok else "No recent scan detected",
        )
    )
    statuses.append("ok" if monitor_ok else "warn")

    overall = "ok"
    if "warn" in statuses:
        overall = "degraded"
    if statuses.count("error") > 0:
        overall = "error"

    opps = analytics.get_top_opportunities(limit=100, min_score=0)

    return SystemHealthResponse(
        overall=overall,
        components=components,
        last_scan=get_last_scan_time(),
        opportunities_count=len(opps),
        monitor_running=monitor_ok,
    )


@router.get("/dashboard", response_model=DashboardKPIs)
def dashboard_kpis(analytics: MarketAnalytics = Depends(get_analytics)) -> DashboardKPIs:
    from backend.api.endpoints.positions import portfolio_summary
    from backend.deps import get_risk_manager

    summary = portfolio_summary(get_risk_manager())
    opps = analytics.get_top_opportunities(limit=100, min_score=0)

    return DashboardKPIs(
        total_opportunities=len(opps),
        portfolio_heat_pct=summary.portfolio_heat_pct,
        today_pnl_rub=summary.today_pnl_rub,
        win_rate_pct=summary.win_rate_pct,
        last_scan=get_last_scan_time(),
        balance=summary.balance,
        open_positions=summary.open_positions_count,
    )
