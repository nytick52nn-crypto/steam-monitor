"""Historical simulation with risk-managed position sizing."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.config import STEAM_MARKET_FEE_PCT
from app.indicators import add_indicators
from app.logger import setup_logging
from app.risk_manager import RiskManager
from app.trading_engine import get_detailed_trade_signal

log = setup_logging("backtester")


@dataclass
class BacktestTrade:
    item_name: str
    entry_price: float
    exit_price: float
    quantity: float
    cost: float
    pnl_rub: float
    pnl_pct: float
    stop_loss: float


@dataclass
class BacktestResult:
    item_name: str
    starting_balance: float
    ending_balance: float
    trades: list[BacktestTrade] = field(default_factory=list)
    blocked_buys: int = 0
    signals_seen: int = 0

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @property
    def total_pnl(self) -> float:
        return self.ending_balance - self.starting_balance


class Backtester:
    """Walk price history, apply strategy signals and RiskManager gates."""

    def __init__(
        self,
        risk_manager: RiskManager | None = None,
        *,
        min_history: int = 20,
        starting_balance: float = 10_000.0,
    ) -> None:
        self.risk = risk_manager or RiskManager()
        self.min_history = max(5, int(min_history))
        self.starting_balance = max(0.0, float(starting_balance))

    def _prices_to_dataframe(
        self, prices: list[float], volumes: list[int] | None
    ) -> pd.DataFrame:
        vols = volumes if volumes else [100] * len(prices)
        df = pd.DataFrame({"price": prices, "volume": vols[: len(prices)]})
        return add_indicators(df)

    def run(
        self,
        item_name: str,
        prices: list[float],
        volumes: list[int] | None = None,
    ) -> BacktestResult:
        """
        Simulate bar-by-bar trading on *prices* with risk rules.

        Never raises; returns partial results on bad input.
        """
        result = BacktestResult(
            item_name=item_name or "unknown",
            starting_balance=self.starting_balance,
            ending_balance=self.starting_balance,
        )

        if not prices or len(prices) < self.min_history:
            log.debug(
                "Backtest skipped %s: need %d prices, got %d",
                item_name,
                self.min_history,
                len(prices or []),
            )
            return result

        balance = self.starting_balance
        open_positions: list[dict] = []
        open_trade: dict | None = None

        try:
            df = self._prices_to_dataframe(prices, volumes)
            df = df.dropna(subset=["rsi", "lower_band", "upper_band"])
        except Exception as exc:
            log.error("Backtest indicator failed for %s: %s", item_name, exc)
            return result

        if len(df) < self.min_history:
            return result

        vol_risk = self.risk.volatility_risk_from_prices(prices)

        for i in range(self.min_history, len(df)):
            window = df.iloc[: i + 1].copy()
            row = window.iloc[-1]
            price = float(row["price"])
            volume = int(row.get("volume", 0) or 0)
            entry_price = open_trade["entry_price"] if open_trade else None

            try:
                signal_result = get_detailed_trade_signal(
                    window,
                    price,
                    volume,
                    fee_pct=STEAM_MARKET_FEE_PCT,
                    entry_price=entry_price,
                )
            except Exception as exc:
                log.debug("Backtest signal error at bar %d: %s", i, exc)
                continue

            signal = signal_result.get("signal", "HOLD")
            result.signals_seen += 1

            if signal == "BUY" and open_trade is None:
                profit_score = _safe_profit_score(signal_result)
                allowed, reason = self.risk.is_trade_allowed(
                    item_name,
                    profit_score,
                    vol_risk,
                    balance,
                    open_positions,
                )
                if not allowed:
                    result.blocked_buys += 1
                    log.debug("Backtest BUY blocked %s: %s", item_name, reason)
                    continue

                size = self.risk.calculate_position_size(
                    balance, profit_score, vol_risk, item_name
                )
                if size <= 0 or price <= 0:
                    result.blocked_buys += 1
                    continue

                qty = round(size / price, 4)
                cost = round(price * qty, 2)
                if cost > balance:
                    result.blocked_buys += 1
                    continue

                stop = self.risk.calculate_dynamic_stop_loss(price, vol_risk)
                open_trade = {
                    "item_name": item_name,
                    "entry_price": price,
                    "quantity": qty,
                    "cost": cost,
                    "stop_loss": stop,
                }
                open_positions.append(open_trade)
                balance -= cost
                log.debug(
                    "Backtest BUY %s @ %.2f qty=%.4f cost=%.2f",
                    item_name,
                    price,
                    qty,
                    cost,
                )

            elif signal == "SELL" and open_trade is not None:
                qty = float(open_trade["quantity"])
                entry = float(open_trade["entry_price"])
                cost = float(open_trade["cost"])
                net_per = price * (1 - STEAM_MARKET_FEE_PCT / 100.0)
                revenue = net_per * qty
                pnl = round(revenue - cost, 2)
                pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
                balance += revenue

                result.trades.append(
                    BacktestTrade(
                        item_name=item_name,
                        entry_price=entry,
                        exit_price=price,
                        quantity=qty,
                        cost=cost,
                        pnl_rub=pnl,
                        pnl_pct=pnl_pct,
                        stop_loss=float(open_trade.get("stop_loss", 0)),
                    )
                )
                open_positions = []
                open_trade = None

            elif open_trade is not None:
                stop = float(open_trade.get("stop_loss", 0))
                if stop > 0 and price <= stop:
                    qty = float(open_trade["quantity"])
                    cost = float(open_trade["cost"])
                    entry = float(open_trade["entry_price"])
                    net_per = price * (1 - STEAM_MARKET_FEE_PCT / 100.0)
                    revenue = net_per * qty
                    pnl = round(revenue - cost, 2)
                    pnl_pct = (pnl / cost * 100.0) if cost > 0 else 0.0
                    balance += revenue
                    result.trades.append(
                        BacktestTrade(
                            item_name=item_name,
                            entry_price=entry,
                            exit_price=price,
                            quantity=qty,
                            cost=cost,
                            pnl_rub=pnl,
                            pnl_pct=pnl_pct,
                            stop_loss=stop,
                        )
                    )
                    open_positions = []
                    open_trade = None

        result.ending_balance = round(balance, 2)
        log.info(
            "Backtest %s: trades=%d blocked_buys=%d pnl=%.2f",
            item_name,
            result.trade_count,
            result.blocked_buys,
            result.total_pnl,
        )
        return result


def _safe_profit_score(signal_result: dict) -> float:
    est = signal_result.get("estimated_profit_pct")
    try:
        return max(0.0, min(100.0, float(est or 0) * 3.0))
    except (TypeError, ValueError):
        return 70.0
