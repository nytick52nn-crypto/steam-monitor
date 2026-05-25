from __future__ import annotations

import csv
import io
import math
from datetime import datetime

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.paper_trading import get_closed_positions
from backend.schemas.trades import TradeRow, TradesResponse

router = APIRouter(prefix="/trades", tags=["trades"])


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            return None


@router.get("", response_model=TradesResponse)
def list_trades(
    search: str = Query(""),
    pnl_min: float | None = None,
    pnl_max: float | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
) -> TradesResponse:
    rows = get_closed_positions()
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    filtered: list[dict] = []

    for r in rows:
        name = r["item_name"]
        if search and search.lower() not in name.lower():
            continue
        pnl = r.get("pnl_rub")
        if pnl_min is not None and (pnl is None or pnl < pnl_min):
            continue
        if pnl_max is not None and (pnl is None or pnl > pnl_max):
            continue
        closed_at = r.get("closed_at")
        if df and closed_at and closed_at < df:
            continue
        if dt and closed_at and closed_at > dt:
            continue
        filtered.append(r)

    total = len(filtered)
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    start = (page - 1) * page_size
    page_rows = filtered[start : start + page_size]

    total_pnl = sum(float(t.get("pnl_rub") or 0) for t in filtered)
    wins = sum(1 for t in filtered if (t.get("pnl_rub") or 0) > 0)
    summary = {
        "total_trades": total,
        "total_pnl_rub": round(total_pnl, 2),
        "win_rate_pct": round((wins / total) * 100, 1) if total else None,
        "avg_pnl_rub": round(total_pnl / total, 2) if total else 0,
    }

    items = [TradeRow(**t) for t in page_rows]
    return TradesResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        summary=summary,
    )


@router.get("/export")
def export_trades(
    search: str = Query(""),
    pnl_min: float | None = None,
    pnl_max: float | None = None,
) -> StreamingResponse:
    resp = list_trades(
        search=search,
        pnl_min=pnl_min,
        pnl_max=pnl_max,
        page=1,
        page_size=10_000,
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "item_name",
            "entry_price",
            "exit_price",
            "quantity",
            "pnl_rub",
            "pnl_pct",
            "opened_at",
            "closed_at",
        ]
    )
    for t in resp.items:
        writer.writerow(
            [
                t.id,
                t.item_name,
                t.entry_price,
                t.exit_price,
                t.quantity,
                t.pnl_rub,
                t.pnl_pct,
                t.opened_at,
                t.closed_at,
            ]
        )
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades.csv"},
    )
