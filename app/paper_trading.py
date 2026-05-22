"""Paper BUY execution: open positions backed by the virtual wallet."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.config import MAX_POSITION_PCT, PAPER_TRADING_ENABLED
from app.database import SessionLocal
from app.logger import setup_logging
from app.models import OpenPosition
from app.wallet import InsufficientBalanceError, get_balance, withdraw

log = setup_logging("paper_trading")

POSITION_STATUS_OPEN = "open"


def max_position_cost(balance: float) -> float:
    """Maximum spend allowed for a single BUY (₽)."""
    if MAX_POSITION_PCT <= 0:
        return 0.0
    return balance * (MAX_POSITION_PCT / 100.0)


def has_open_position(item_name: str, db: Session | None = None) -> bool:
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        return (
            db.query(OpenPosition)
            .filter(
                OpenPosition.item_name == item_name,
                OpenPosition.status == POSITION_STATUS_OPEN,
            )
            .first()
            is not None
        )
    finally:
        if own_session:
            db.close()


def get_open_positions() -> list[dict]:
    db = SessionLocal()
    try:
        rows = (
            db.query(OpenPosition)
            .filter(OpenPosition.status == POSITION_STATUS_OPEN)
            .order_by(OpenPosition.opened_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "item_name": r.item_name,
                "entry_price": float(r.entry_price),
                "quantity": float(r.quantity),
                "cost": float(r.cost),
                "status": r.status,
                "signal": r.signal,
                "opened_at": r.opened_at,
            }
            for r in rows
        ]
    finally:
        db.close()


def execute_paper_buy(
    item_name: str,
    entry_price: float,
    *,
    hash_name: str | None = None,
    quantity: float = 1.0,
) -> OpenPosition | None:
    """
    Open a paper position on BUY: withdraw cost from wallet, persist to SQLite.

    Returns the new position, or None if the buy was skipped (disabled, duplicate,
    over max size, or insufficient balance).
    """
    if not PAPER_TRADING_ENABLED:
        log.debug("Paper trading disabled, skipping BUY for %s", item_name)
        return None

    if entry_price <= 0 or quantity <= 0:
        log.warning("Invalid BUY params for %s: price=%s qty=%s", item_name, entry_price, quantity)
        return None

    cost = round(entry_price * quantity, 2)
    balance = get_balance()
    cap = max_position_cost(balance)

    if cost > cap:
        log.info(
            "Paper BUY skipped %s: cost %.2f > max position %.2f (%.0f%% of %.2f)",
            item_name,
            cost,
            cap,
            MAX_POSITION_PCT,
            balance,
        )
        return None

    db = SessionLocal()
    try:
        if has_open_position(item_name, db):
            log.info("Paper BUY skipped %s: open position already exists", item_name)
            return None

        try:
            withdraw(cost, note=f"paper BUY {item_name}")
        except InsufficientBalanceError:
            log.info(
                "Paper BUY skipped %s: insufficient balance (need %.2f, have %.2f)",
                item_name,
                cost,
                balance,
            )
            return None

        position = OpenPosition(
            item_name=item_name,
            hash_name=hash_name or item_name,
            entry_price=entry_price,
            quantity=quantity,
            cost=cost,
            status=POSITION_STATUS_OPEN,
            signal="BUY",
            opened_at=datetime.utcnow(),
        )
        db.add(position)
        db.commit()
        db.refresh(position)
        log.info(
            "Paper BUY opened id=%s %s @ %.2f cost=%.2f balance_after=%.2f",
            position.id,
            item_name,
            entry_price,
            cost,
            get_balance(),
        )
        return position
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
