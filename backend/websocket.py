"""WebSocket hub for real-time dashboard updates."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from app.analytics import MarketAnalytics
from app.paper_trading import get_open_positions
from backend.utils import get_last_scan_time, parse_log_file


class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        payload = json.dumps(message, default=str)
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def _build_snapshot() -> dict[str, Any]:
    analytics = MarketAnalytics()
    opportunities = analytics.get_top_opportunities(limit=15, min_score=0)
    positions = get_open_positions()
    logs, _ = parse_log_file(limit=30)
    return {
        "type": "snapshot",
        "last_scan": get_last_scan_time(),
        "opportunities": opportunities,
        "positions": positions,
        "logs": logs[-10:],
    }


async def websocket_endpoint(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await websocket.send_text(
            json.dumps(await _build_snapshot(), default=str)
        )
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except asyncio.TimeoutError:
                await websocket.send_text(
                    json.dumps(await _build_snapshot(), default=str)
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)


async def push_event(event_type: str, payload: dict[str, Any]) -> None:
    await manager.broadcast({"type": event_type, **payload})
