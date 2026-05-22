"""Steam Market fee and ROI helpers."""

from dataclasses import dataclass


@dataclass
class TradeMetrics:
    buy_price: float
    sell_price: float
    steam_fee_pct: float
    fee_amount: float
    net_after_fee: float
    gross_profit: float
    roi_pct: float


def steam_fee_amount(gross_price: float, fee_pct: float) -> float:
    return gross_price * (fee_pct / 100.0)


def net_after_steam_fee(gross_price: float, fee_pct: float) -> float:
    return gross_price - steam_fee_amount(gross_price, fee_pct)


def calc_buy_metrics(
    buy_price: float,
    target_sell_price: float,
    fee_pct: float,
) -> TradeMetrics:
    fee = steam_fee_amount(target_sell_price, fee_pct)
    net = target_sell_price - fee
    profit = net - buy_price
    roi = (profit / buy_price * 100.0) if buy_price > 0 else 0.0
    return TradeMetrics(
        buy_price=buy_price,
        sell_price=target_sell_price,
        steam_fee_pct=fee_pct,
        fee_amount=fee,
        net_after_fee=net,
        gross_profit=profit,
        roi_pct=roi,
    )


def calc_sell_metrics(
    entry_price: float,
    sell_price: float,
    fee_pct: float,
) -> TradeMetrics:
    fee = steam_fee_amount(sell_price, fee_pct)
    net = sell_price - fee
    profit = net - entry_price
    roi = (profit / entry_price * 100.0) if entry_price > 0 else 0.0
    return TradeMetrics(
        buy_price=entry_price,
        sell_price=sell_price,
        steam_fee_pct=fee_pct,
        fee_amount=fee,
        net_after_fee=net,
        gross_profit=profit,
        roi_pct=roi,
    )
