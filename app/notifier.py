import asyncio
from pathlib import Path

from telegram import Bot
from telegram.constants import ParseMode
from telegram.request import HTTPXRequest

from app.config import (
    STEAM_MARKET_FEE_PCT,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ENABLED,
    TELEGRAM_MAX_RETRIES,
    TELEGRAM_PROXY_URL,
    TELEGRAM_REQUEST_TIMEOUT,
    telegram_config_status,
)
from app.logger import setup_logging
from app.roi import TradeMetrics

log = setup_logging("notifier")


def is_telegram_configured() -> bool:
    return telegram_config_status()["ready"]


def _build_bot() -> Bot:
    timeout = TELEGRAM_REQUEST_TIMEOUT
    request = HTTPXRequest(
        connect_timeout=timeout,
        read_timeout=timeout,
        write_timeout=timeout,
        pool_timeout=timeout,
        proxy=TELEGRAM_PROXY_URL,
    )
    if TELEGRAM_PROXY_URL:
        log.info("Telegram using proxy: %s", TELEGRAM_PROXY_URL.split("@")[-1])
    return Bot(token=TELEGRAM_BOT_TOKEN, request=request)


async def _send_with_retries(send_coro_factory, label: str) -> bool:
    last_error = None
    for attempt in range(1, TELEGRAM_MAX_RETRIES + 1):
        try:
            msg = await send_coro_factory()
            log.info("Telegram %s delivered (message_id=%s, attempt=%d)", label, msg.message_id, attempt)
            return True
        except Exception as exc:
            last_error = exc
            log.warning("Telegram %s attempt %d/%d failed: %s", label, attempt, TELEGRAM_MAX_RETRIES, exc)
            if attempt < TELEGRAM_MAX_RETRIES:
                await asyncio.sleep(2 * attempt)
    log.error("Telegram %s FAILED after %d attempts: %s", label, TELEGRAM_MAX_RETRIES, last_error)
    return False


def _fmt_money(value: float) -> str:
    return f"{value:,.2f}".replace(",", " ")


def _metrics_block(metrics: TradeMetrics, label: str) -> str:
    roi_sign = "+" if metrics.roi_pct >= 0 else ""
    return (
        f"<b>{label}</b>\n"
        f"Buy / entry: {_fmt_money(metrics.buy_price)} ₽\n"
        f"Sell target: {_fmt_money(metrics.sell_price)} ₽\n"
        f"Steam fee ({metrics.steam_fee_pct:.0f}%): {_fmt_money(metrics.fee_amount)} ₽\n"
        f"Net after fee: {_fmt_money(metrics.net_after_fee)} ₽\n"
        f"Profit: {_fmt_money(metrics.gross_profit)} ₽\n"
        f"ROI: <b>{roi_sign}{metrics.roi_pct:.2f}%</b>"
    )


def format_buy_alert(
    item_name: str,
    price: float,
    rsi: float,
    metrics: TradeMetrics,
    volume: int,
) -> str:
    return (
        "🟢 <b>BUY SIGNAL</b>\n\n"
        f"<b>{item_name}</b>\n"
        f"Current price: {_fmt_money(price)} ₽\n"
        f"RSI: {rsi:.1f}\n"
        f"Volume: {volume}\n\n"
        f"{_metrics_block(metrics, 'If sold at target')}\n\n"
        "<i>Steam Community Market — fee applied on sale.</i>"
    )


def format_sell_alert(
    item_name: str,
    price: float,
    rsi: float,
    metrics: TradeMetrics,
    volume: int,
) -> str:
    return (
        "🔴 <b>SELL SIGNAL</b>\n\n"
        f"<b>{item_name}</b>\n"
        f"Current price: {_fmt_money(price)} ₽\n"
        f"RSI: {rsi:.1f}\n"
        f"Volume: {volume}\n\n"
        f"{_metrics_block(metrics, 'Sell now vs entry')}\n\n"
        f"<i>Steam fee: {STEAM_MARKET_FEE_PCT:.0f}% deducted from sale.</i>"
    )


async def _send_message_async(text: str) -> bool:
    bot = _build_bot()

    async def _do_send():
        return await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode=ParseMode.HTML,
        )

    return await _send_with_retries(_do_send, "message")


async def _send_photo_async(text: str, chart_path: Path) -> bool:
    bot = _build_bot()

    async def _do_send():
        with chart_path.open("rb") as photo:
            return await bot.send_photo(
                chat_id=TELEGRAM_CHAT_ID,
                photo=photo,
                caption=text[:1024],
                parse_mode=ParseMode.HTML,
            )

    return await _send_with_retries(_do_send, f"photo:{chart_path.name}")


async def _send_alert_async(text: str, chart_path: Path | None) -> bool:
    if chart_path and chart_path.exists():
        return await _send_photo_async(text, chart_path)
    return await _send_message_async(text)


def send_raw_message(text: str, chart_path: Path | None = None) -> bool:
    if not is_telegram_configured():
        log.warning("Telegram not configured — message not sent")
        return False
    return asyncio.run(_send_alert_async(text, chart_path))


def send_startup_test() -> bool:
    status = telegram_config_status()
    log.info(
        "Telegram config: enabled=%s token_loaded=%s chat_loaded=%s ready=%s",
        status["enabled"],
        status["token_loaded"],
        status["chat_loaded"],
        status["ready"],
    )

    if not status["ready"]:
        for issue in status["issues"]:
            log.warning("Telegram setup issue: %s", issue)
        return False

    text = (
        "✅ <b>Steam Monitor started</b>\n\n"
        "Telegram alerts are active.\n"
        "You will receive BUY/SELL signals with charts and ROI."
    )
    log.info("Sending Telegram startup test message...")
    ok = send_raw_message(text)
    if ok:
        log.info("Telegram startup test: SUCCESS")
    else:
        log.error("Telegram startup test: FAILED")
    return ok


def send_sell_alert(trade: dict) -> bool:
    """Send a Telegram alert for a closed paper trade."""
    if not is_telegram_configured():
        log.debug("Telegram not configured, skipping sell alert for %s", trade.get("item_name"))
        return False

    from app.wallet import get_balance

    balance = get_balance()
    pnl_sign = "+" if trade["pnl_rub"] >= 0 else ""
    text = (
        "\U0001f534 <b>ЗАКРЫТО:</b> {item_name}\n"
        "Вход: {entry:.0f}₽ → Выход: {exit:.0f}₽\n"
        "PnL: {pnl_sign}{pnl_rub:.0f}₽ ({pnl_sign}{pnl_pct:.1f}%)\n"
        "Баланс: {balance:.0f}₽"
    ).format(
        item_name=trade["item_name"],
        entry=trade["entry_price"],
        exit=trade["exit_price"],
        pnl_sign=pnl_sign,
        pnl_rub=trade["pnl_rub"],
        pnl_pct=trade["pnl_pct"],
        balance=balance,
    )

    log.info("Sending Telegram SELL close alert for %s", trade["item_name"])
    ok = send_raw_message(text)
    if ok:
        log.info("Telegram SELL close alert for %s: DELIVERED", trade["item_name"])
    else:
        log.error("Telegram SELL close alert for %s: FAILED", trade["item_name"])
    return ok


def send_signal_alert(
    signal: str,
    item_name: str,
    price: float,
    rsi: float,
    metrics: TradeMetrics,
    volume: int,
    chart_path: Path | None,
) -> bool:
    if not is_telegram_configured():
        log.debug("Telegram not configured, skipping %s alert for %s", signal, item_name)
        return False

    if signal == "BUY":
        text = format_buy_alert(item_name, price, rsi, metrics, volume)
    elif signal == "SELL":
        text = format_sell_alert(item_name, price, rsi, metrics, volume)
    else:
        return False

    log.info("Sending Telegram %s alert for %s (chart=%s)", signal, item_name, chart_path)
    ok = asyncio.run(_send_alert_async(text, chart_path))
    if ok:
        log.info("Telegram %s alert for %s: DELIVERED", signal, item_name)
    else:
        log.error("Telegram %s alert for %s: FAILED", signal, item_name)
    return ok
