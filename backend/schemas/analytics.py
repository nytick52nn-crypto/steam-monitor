from pydantic import BaseModel, Field


class OpportunityRow(BaseModel):
    item_name: str
    profit_score: float
    price_change_pct: float | None = None
    momentum_pct: float = 0.0
    momentum_score: float | None = None
    liquidity_score: float | None = None
    volatility_score: float | None = None
    spread_stability_score: float | None = None
    liquidity_label: str = "n/a"
    volatility_label: str = "n/a"
    current_price: float | None = None
    on_watchlist: bool = False


class OpportunityFilters(BaseModel):
    search: str = ""
    profit_min: float | None = None
    profit_max: float | None = None
    liquidity_min: float | None = None
    volatility_min: float | None = None
    momentum_min: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    watchlist_only: bool = False
    page: int = Field(1, ge=1)
    page_size: int = Field(25, ge=5, le=200)
    sort_by: str = "profit_score"
    sort_dir: str = "desc"


class OpportunitiesResponse(BaseModel):
    items: list[OpportunityRow]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProfitScoreBreakdown(BaseModel):
    item_name: str
    profit_score: float
    price_change_pct: float | None = None
    momentum_pct: float = 0.0
    momentum_score: float | None = None
    liquidity_score: float | None = None
    volatility_score: float | None = None
    spread_stability_score: float | None = None
    liquidity_label: str = "n/a"
    volatility_label: str = "n/a"
    price_movement_component: float | None = None


class PricePoint(BaseModel):
    timestamp: str
    price: float
    volume: int = 0


class ItemHistoryResponse(BaseModel):
    item_name: str
    days: int
    points: list[PricePoint]


class ItemRiskResponse(BaseModel):
    item_name: str
    profit_score: float
    volatility_risk: float
    has_analytics: bool
    stop_loss_preview: float | None = None
    trade_allowed: bool = False
    trade_reason: str = ""
    portfolio_heat_pct: float = 0.0


class FilterPreset(BaseModel):
    id: str
    name: str
    filters: dict


class FilterPresetCreate(BaseModel):
    name: str
    filters: dict
