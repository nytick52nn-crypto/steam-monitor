from __future__ import annotations

import math

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics import MarketAnalytics, run_cycle_analytics
from backend.deps import get_analytics, get_risk_manager
from backend.schemas.analytics import (
    FilterPreset,
    FilterPresetCreate,
    ItemHistoryResponse,
    ItemRiskResponse,
    OpportunitiesResponse,
    OpportunityRow,
    ProfitScoreBreakdown,
)
from backend.schemas.common import MessageResponse
from backend.utils import (
    add_to_watchlist,
    delete_filter_preset,
    get_filter_presets,
    get_latest_price,
    get_watchlist,
    is_on_watchlist,
    remove_from_watchlist,
    save_filter_preset,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _price_movement_component(change_pct: float | None) -> float | None:
    if change_pct is None:
        return None
    return max(0.0, min(100.0, 50.0 + change_pct * 2.0))


def _fetch_all_opportunities(analytics: MarketAnalytics, limit: int = 80) -> list[dict]:
    return analytics.get_top_opportunities(limit=limit, min_score=0.0)


def _apply_filters(
    rows: list[dict],
    *,
    search: str,
    profit_min: float | None,
    profit_max: float | None,
    liquidity_min: float | None,
    volatility_min: float | None,
    momentum_min: float | None,
    price_min: float | None,
    price_max: float | None,
    watchlist_only: bool,
) -> list[dict]:
    watchlist = set(get_watchlist())
    out: list[dict] = []
    for row in rows:
        name = row["item_name"]
        if watchlist_only and name not in watchlist:
            continue
        if search and search.lower() not in name.lower():
            continue
        score = row.get("profit_score", 0)
        if profit_min is not None and score < profit_min:
            continue
        if profit_max is not None and score > profit_max:
            continue
        liq = row.get("liquidity_score")
        if liquidity_min is not None and (liq is None or liq < liquidity_min):
            continue
        vol = row.get("volatility_score")
        if volatility_min is not None and (vol is None or vol < volatility_min):
            continue
        mom = row.get("momentum_score")
        if momentum_min is not None and (mom is None or mom < momentum_min):
            continue
        price = get_latest_price(name)
        if price_min is not None and (price is None or price < price_min):
            continue
        if price_max is not None and (price is None or price > price_max):
            continue
        row = dict(row)
        row["current_price"] = price
        row["on_watchlist"] = name in watchlist
        out.append(row)
    return out


def _sort_rows(rows: list[dict], sort_by: str, sort_dir: str) -> list[dict]:
    reverse = sort_dir.lower() != "asc"
    key_map = {
        "profit_score": lambda r: r.get("profit_score", 0),
        "liquidity_score": lambda r: r.get("liquidity_score") or 0,
        "volatility_score": lambda r: r.get("volatility_score") or 0,
        "momentum_score": lambda r: r.get("momentum_score") or 0,
        "current_price": lambda r: r.get("current_price") or 0,
        "item_name": lambda r: r.get("item_name", ""),
    }
    key_fn = key_map.get(sort_by, key_map["profit_score"])
    return sorted(rows, key=key_fn, reverse=reverse)


@router.get("/opportunities", response_model=OpportunitiesResponse)
def list_opportunities(
    search: str = Query(""),
    profit_min: float | None = None,
    profit_max: float | None = None,
    liquidity_min: float | None = None,
    volatility_min: float | None = None,
    momentum_min: float | None = None,
    price_min: float | None = None,
    price_max: float | None = None,
    watchlist_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    sort_by: str = "profit_score",
    sort_dir: str = "desc",
    analytics: MarketAnalytics = Depends(get_analytics),
) -> OpportunitiesResponse:
    raw = _fetch_all_opportunities(analytics)
    filtered = _apply_filters(
        raw,
        search=search.strip(),
        profit_min=profit_min,
        profit_max=profit_max,
        liquidity_min=liquidity_min,
        volatility_min=volatility_min,
        momentum_min=momentum_min,
        price_min=price_min,
        price_max=price_max,
        watchlist_only=watchlist_only,
    )
    sorted_rows = _sort_rows(filtered, sort_by, sort_dir)
    total = len(sorted_rows)
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    start = (page - 1) * page_size
    page_rows = sorted_rows[start : start + page_size]
    items = [OpportunityRow(**r) for r in page_rows]
    return OpportunitiesResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/items/{item_name:path}/detail", response_model=ProfitScoreBreakdown)
def item_detail(
    item_name: str,
    analytics: MarketAnalytics = Depends(get_analytics),
) -> ProfitScoreBreakdown:
    row = analytics.calculate_profit_score(item_name)
    if not row:
        raise HTTPException(404, f"Insufficient history for {item_name}")
    return ProfitScoreBreakdown(
        **row,
        price_movement_component=_price_movement_component(row.get("price_change_pct")),
    )


@router.get("/items/{item_name:path}/history", response_model=ItemHistoryResponse)
def item_history(
    item_name: str,
    days: int = Query(7, ge=1, le=90),
    analytics: MarketAnalytics = Depends(get_analytics),
) -> ItemHistoryResponse:
    hours = days * 24
    history = analytics.get_price_history(item_name, hours=hours)
    points = [
        {
            "timestamp": h["timestamp"],
            "price": h["price"],
            "volume": h.get("volume", 0),
        }
        for h in history
    ]
    return ItemHistoryResponse(item_name=item_name, days=days, points=points)


@router.get("/items/{item_name:path}/risk", response_model=ItemRiskResponse)
def item_risk(
    item_name: str,
    analytics: MarketAnalytics = Depends(get_analytics),
    risk=Depends(get_risk_manager),
) -> ItemRiskResponse:
    from app.paper_trading import get_open_positions
    from app.wallet import get_balance

    metrics = risk.get_item_risk_metrics(item_name)
    balance = get_balance()
    positions = get_open_positions()
    heat = risk.portfolio_heat_ratio(positions, balance) * 100
    price = get_latest_price(item_name)
    stop = None
    if price and price > 0:
        stop = risk.calculate_dynamic_stop_loss(price, metrics["volatility_risk"])
    allowed, reason = risk.is_trade_allowed(
        item_name,
        metrics["profit_score"],
        metrics["volatility_risk"],
        balance,
        positions,
    )
    return ItemRiskResponse(
        item_name=item_name,
        profit_score=metrics["profit_score"],
        volatility_risk=metrics["volatility_risk"],
        has_analytics=metrics["has_analytics"],
        stop_loss_preview=stop,
        trade_allowed=allowed,
        trade_reason=reason,
        portfolio_heat_pct=round(heat, 2),
    )


@router.post("/run", response_model=MessageResponse)
def run_analytics() -> MessageResponse:
    run_cycle_analytics()
    return MessageResponse(message="Analytics cycle completed", ok=True)


@router.get("/watchlist", response_model=list[str])
def watchlist_get() -> list[str]:
    return get_watchlist()


@router.post("/watchlist/{item_name:path}", response_model=list[str])
def watchlist_add(item_name: str) -> list[str]:
    return add_to_watchlist(item_name)


@router.delete("/watchlist/{item_name:path}", response_model=list[str])
def watchlist_remove(item_name: str) -> list[str]:
    return remove_from_watchlist(item_name)


@router.get("/filter-presets", response_model=list[FilterPreset])
def list_presets() -> list[FilterPreset]:
    return [FilterPreset(**p) for p in get_filter_presets()]


@router.post("/filter-presets", response_model=FilterPreset)
def create_preset(body: FilterPresetCreate) -> FilterPreset:
    saved = save_filter_preset(body.name, body.filters)
    return FilterPreset(**saved)


@router.delete("/filter-presets/{preset_id}", response_model=MessageResponse)
def remove_preset(preset_id: str) -> MessageResponse:
    if not delete_filter_preset(preset_id):
        raise HTTPException(404, "Preset not found")
    return MessageResponse(message="Preset deleted")
