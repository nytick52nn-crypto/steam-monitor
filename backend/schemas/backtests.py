from pydantic import BaseModel, Field


class BacktestRunRequest(BaseModel):
    item_name: str
    starting_balance: float = Field(10_000.0, gt=0)


class BacktestTradeRow(BaseModel):
    item_name: str
    entry_price: float
    exit_price: float
    quantity: float
    cost: float
    pnl_rub: float
    pnl_pct: float
    stop_loss: float


class BacktestResultResponse(BaseModel):
    id: str
    item_name: str
    starting_balance: float
    ending_balance: float
    total_pnl: float
    trade_count: int
    blocked_buys: int
    signals_seen: int
    trades: list[BacktestTradeRow]
    created_at: str


class BacktestHistoryResponse(BaseModel):
    items: list[BacktestResultResponse]
