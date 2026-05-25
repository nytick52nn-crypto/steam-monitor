from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.backtester import Backtester
from backend.deps import get_analytics, get_risk_manager
from backend.schemas.backtests import (
    BacktestHistoryResponse,
    BacktestResultResponse,
    BacktestRunRequest,
    BacktestTradeRow,
)
from backend.utils import append_backtest_result, get_backtest_history

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("", response_model=BacktestHistoryResponse)
def backtest_history() -> BacktestHistoryResponse:
    items = [
        BacktestResultResponse(
            id=h["id"],
            item_name=h["item_name"],
            starting_balance=h["starting_balance"],
            ending_balance=h["ending_balance"],
            total_pnl=h["total_pnl"],
            trade_count=h["trade_count"],
            blocked_buys=h["blocked_buys"],
            signals_seen=h["signals_seen"],
            trades=[BacktestTradeRow(**t) for t in h.get("trades", [])],
            created_at=h["created_at"],
        )
        for h in get_backtest_history()
    ]
    return BacktestHistoryResponse(items=items)


@router.post("/run", response_model=BacktestResultResponse)
def run_backtest(
    body: BacktestRunRequest,
    analytics=Depends(get_analytics),
    risk=Depends(get_risk_manager),
) -> BacktestResultResponse:
    history = analytics.get_price_history(body.item_name, hours=24 * 90)
    if len(history) < 20:
        raise HTTPException(
            400,
            f"Need at least 20 price snapshots for {body.item_name}",
        )
    prices = [h["price"] for h in history]
    volumes = [h.get("volume", 0) for h in history]

    bt = Backtester(risk_manager=risk, starting_balance=body.starting_balance)
    result = bt.run(body.item_name, prices, volumes)

    trades = [
        BacktestTradeRow(
            item_name=t.item_name,
            entry_price=t.entry_price,
            exit_price=t.exit_price,
            quantity=t.quantity,
            cost=t.cost,
            pnl_rub=t.pnl_rub,
            pnl_pct=t.pnl_pct,
            stop_loss=t.stop_loss,
        )
        for t in result.trades
    ]

    payload = {
        "item_name": result.item_name,
        "starting_balance": result.starting_balance,
        "ending_balance": result.ending_balance,
        "total_pnl": result.total_pnl,
        "trade_count": result.trade_count,
        "blocked_buys": result.blocked_buys,
        "signals_seen": result.signals_seen,
        "trades": [t.model_dump() for t in trades],
    }
    saved = append_backtest_result(payload)
    return BacktestResultResponse(
        id=saved["id"],
        created_at=saved["created_at"],
        trades=trades,
        **{k: payload[k] for k in payload if k != "trades"},
    )
