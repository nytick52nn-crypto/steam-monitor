from pydantic import BaseModel


class HealthComponent(BaseModel):
    name: str
    status: str
    detail: str = ""


class SystemHealthResponse(BaseModel):
    overall: str
    components: list[HealthComponent]
    last_scan: str | None = None
    opportunities_count: int = 0
    monitor_running: bool = False


class DashboardKPIs(BaseModel):
    total_opportunities: int
    portfolio_heat_pct: float
    today_pnl_rub: float
    win_rate_pct: float | None
    last_scan: str | None
    balance: float
    open_positions: int
