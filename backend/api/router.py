from fastapi import APIRouter

from backend.api.endpoints import analytics, backtests, logs, positions, system, trades

api_router = APIRouter(prefix="/api")
api_router.include_router(analytics.router)
api_router.include_router(positions.router)
api_router.include_router(trades.router)
api_router.include_router(backtests.router)
api_router.include_router(system.router)
api_router.include_router(logs.router)
