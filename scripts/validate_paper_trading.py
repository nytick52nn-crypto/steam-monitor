"""Validate paper BUY: open_positions table, wallet withdraw, max position cap."""

import sys

from app.config import MAX_POSITION_PCT
from app.database import SessionLocal, engine
from app.models import Base, OpenPosition
from app.paper_trading import (
    execute_paper_buy,
    get_open_positions,
    has_open_position,
    max_position_cost,
)
from app.wallet import InsufficientBalanceError, get_balance, init_wallet, withdraw


def main() -> int:
    Base.metadata.create_all(bind=engine)
    init_wallet()

    item = "__validate_paper_item__"
    db = SessionLocal()
    try:
        db.query(OpenPosition).filter(OpenPosition.item_name == item).delete()
        db.commit()
    finally:
        db.close()

    balance_before = get_balance()
    cap = max_position_cost(balance_before)
    price_ok = min(50.0, cap * 0.5) if cap > 0 else 50.0
    if price_ok <= 0:
        print("SKIP: wallet balance or MAX_POSITION_PCT too low for test")
        return 0

    pos = execute_paper_buy(item, price_ok)
    if pos is None:
        print("ERROR: expected paper BUY to succeed")
        return 1

    balance_after = get_balance()
    if abs(balance_after - (balance_before - price_ok)) > 0.01:
        print(f"ERROR: balance {balance_after} expected {balance_before - price_ok}")
        return 1

    if not has_open_position(item):
        print("ERROR: open position not found")
        return 1

    dup = execute_paper_buy(item, price_ok)
    if dup is not None:
        print("ERROR: duplicate open position allowed")
        return 1

    expensive = balance_after * (MAX_POSITION_PCT / 100.0) + 1.0
    if expensive <= balance_after:
        over = execute_paper_buy(item + "_2", expensive)
        if over is not None:
            print("ERROR: buy over max position pct should be rejected")
            return 1

    try:
        withdraw(balance_after + 1.0)
        print("ERROR: insufficient balance not blocked")
        return 1
    except InsufficientBalanceError:
        pass

    open_list = get_open_positions()
    if not any(p["item_name"] == item for p in open_list):
        print("ERROR: get_open_positions missing test row")
        return 1

    print("paper trading validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
