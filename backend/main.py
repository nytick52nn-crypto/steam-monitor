"""FastAPI monitoring panel backend."""

from __future__ import annotations

import sys
from pathlib import Path

# Project root on sys.path for `app.*` imports
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router
from backend.websocket import websocket_endpoint

app = FastAPI(
    title="Steam Monitor Panel",
    description="Professional monitoring web panel API",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.websocket("/ws")
async def ws_route(websocket: WebSocket) -> None:
    await websocket_endpoint(websocket)


_frontend_dist = _ROOT / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
