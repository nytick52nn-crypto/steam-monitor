from datetime import datetime

from pydantic import BaseModel, Field


class TradeRow(BaseModel):
    id: int
    item_name: str
    entry_price: float
    exit_price: float | None = None
    quantity: float
    pnl_rub: float | None = None
    pnl_pct: float | None = None
    opened_at: datetime | None = None
    closed_at: datetime | None = None


class TradeFilters(BaseModel):
    search: str = ""
    pnl_min: float | None = None
    pnl_max: float | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=5, le=200)


class TradesResponse(BaseModel):
    items: list[TradeRow]
    total: int
    page: int
    page_size: int
    total_pages: int
    summary: dict
