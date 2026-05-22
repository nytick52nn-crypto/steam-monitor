from datetime import datetime

from sqlalchemy.orm import Session

from app.config import WALLET_INITIAL_BALANCE
from app.database import SessionLocal
from app.logger import setup_logging
from app.models import Wallet

log = setup_logging("wallet")

WALLET_ID = 1


class InsufficientBalanceError(Exception):
    """Raised when withdraw would make balance negative."""


def _get_wallet(db: Session, *, create: bool = False) -> Wallet | None:
    wallet = db.query(Wallet).filter(Wallet.id == WALLET_ID).first()
    if wallet or not create:
        return wallet

    wallet = Wallet(
        id=WALLET_ID,
        balance=WALLET_INITIAL_BALANCE,
        starting_balance=WALLET_INITIAL_BALANCE,
        updated_at=datetime.utcnow(),
    )
    db.add(wallet)
    db.commit()
    db.refresh(wallet)
    log.info(
        "Virtual wallet created: balance=%.2f starting=%.2f",
        wallet.balance,
        wallet.starting_balance,
    )
    return wallet


def init_wallet() -> Wallet:
    db = SessionLocal()
    try:
        return _get_wallet(db, create=True)
    finally:
        db.close()


def get_wallet_snapshot() -> dict:
    db = SessionLocal()
    try:
        wallet = _get_wallet(db, create=True)
        return {
            "balance": float(wallet.balance),
            "starting_balance": float(wallet.starting_balance),
            "pnl_placeholder": float(wallet.balance) - float(wallet.starting_balance),
            "updated_at": wallet.updated_at,
        }
    finally:
        db.close()


def get_balance() -> float:
    return get_wallet_snapshot()["balance"]


def deposit(amount: float, note: str = "") -> float:
    if amount <= 0:
        raise ValueError("Deposit amount must be positive")

    db = SessionLocal()
    try:
        wallet = _get_wallet(db, create=True)
        wallet.balance = float(wallet.balance) + amount
        wallet.updated_at = datetime.utcnow()
        db.commit()
        log.info("Wallet deposit: +%.2f -> balance=%.2f %s", amount, wallet.balance, note)
        return float(wallet.balance)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def withdraw(amount: float, note: str = "") -> float:
    if amount <= 0:
        raise ValueError("Withdraw amount must be positive")

    db = SessionLocal()
    try:
        wallet = _get_wallet(db, create=True)
        new_balance = float(wallet.balance) - amount
        if new_balance < 0:
            raise InsufficientBalanceError(
                f"Insufficient balance: have {wallet.balance:.2f}, need {amount:.2f}"
            )
        wallet.balance = new_balance
        wallet.updated_at = datetime.utcnow()
        db.commit()
        log.info("Wallet withdraw: -%.2f -> balance=%.2f %s", amount, wallet.balance, note)
        return float(wallet.balance)
    except InsufficientBalanceError:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
