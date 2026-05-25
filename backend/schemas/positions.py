from datetime import datetime

from pydantic import BaseModel


class PositionRow(BaseModel):
    id: int
    item_name: str
    entry_price: float
    quantity: float
    cost: float
    current_price: float | None = None
    unrealized_pnl_rub: float | None = None
    unrealized_pnl_pct: float | None = None
    stop_loss: float | None = None
    opened_at: datetime | None = None


class PortfolioSummary(BaseModel):
    balance: float
    starting_balance: float
    portfolio_heat_pct: float
    open_positions_count: int
    total_exposure_rub: float
    today_pnl_rub: float
    win_rate_pct: float | None = None
