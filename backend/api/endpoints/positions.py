from __future__ import annotations

from fastapi import APIRouter, Depends

from app.paper_trading import get_open_positions
from app.wallet import get_wallet_snapshot
from backend.deps import get_risk_manager
from backend.schemas.positions import PortfolioSummary, PositionRow
from backend.utils import get_latest_price

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionRow])
def list_positions(risk=Depends(get_risk_manager)) -> list[PositionRow]:
    positions = get_open_positions()
    rows: list[PositionRow] = []
    for p in positions:
        current = get_latest_price(p["item_name"])
        entry = float(p["entry_price"])
        qty = float(p["quantity"])
        cost = float(p["cost"])
        unrealized = None
        unrealized_pct = None
        if current and current > 0:
            from app.config import STEAM_MARKET_FEE_PCT

            net = current * (1 - STEAM_MARKET_FEE_PCT / 100.0) * qty
            unrealized = round(net - cost, 2)
            unrealized_pct = round((unrealized / cost) * 100, 2) if cost > 0 else 0.0
        vol_risk = risk.volatility_risk_from_prices(
            [current] if current else []
        )
        stop = risk.calculate_dynamic_stop_loss(entry, vol_risk) if entry > 0 else None
        rows.append(
            PositionRow(
                id=p["id"],
                item_name=p["item_name"],
                entry_price=entry,
                quantity=qty,
                cost=cost,
                current_price=current,
                unrealized_pnl_rub=unrealized,
                unrealized_pnl_pct=unrealized_pct,
                stop_loss=stop,
                opened_at=p.get("opened_at"),
            )
        )
    return rows


@router.get("/summary", response_model=PortfolioSummary)
def portfolio_summary(risk=Depends(get_risk_manager)) -> PortfolioSummary:
    from datetime import datetime, timezone

    wallet = get_wallet_snapshot()
    positions = get_open_positions()
    balance = wallet["balance"]
    heat = risk.portfolio_heat_ratio(positions, balance) * 100
    exposure = sum(float(p["cost"]) for p in positions)

    from app.paper_trading import get_closed_positions

    closed = get_closed_positions()
    today = datetime.now(timezone.utc).date()
    today_pnl = 0.0
    wins = 0
    total_closed = 0
    for t in closed:
        closed_at = t.get("closed_at")
        if closed_at and hasattr(closed_at, "date") and closed_at.date() == today:
            pnl = float(t.get("pnl_rub") or 0)
            today_pnl += pnl
        if t.get("pnl_rub") is not None:
            total_closed += 1
            if float(t["pnl_rub"]) > 0:
                wins += 1

    win_rate = round((wins / total_closed) * 100, 1) if total_closed else None

    return PortfolioSummary(
        balance=balance,
        starting_balance=wallet["starting_balance"],
        portfolio_heat_pct=round(heat, 2),
        open_positions_count=len(positions),
        total_exposure_rub=round(exposure, 2),
        today_pnl_rub=round(today_pnl, 2),
        win_rate_pct=win_rate,
    )
