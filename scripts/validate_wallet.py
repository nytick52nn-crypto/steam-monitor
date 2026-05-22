"""Validate virtual wallet operations."""

import sys

from app.wallet import (
    InsufficientBalanceError,
    deposit,
    get_balance,
    get_wallet_snapshot,
    init_wallet,
    withdraw,
)


def main() -> int:
    init_wallet()
    snap = get_wallet_snapshot()
    print("snapshot:", snap)

    start = get_balance()
    deposit(500.0, note="validate")
    after_dep = get_balance()
    assert after_dep == start + 500, f"deposit failed: {after_dep}"

    withdraw(200.0, note="validate")
    after_wd = get_balance()
    assert after_wd == after_dep - 200, f"withdraw failed: {after_wd}"

    try:
        withdraw(999_999_999.0)
        print("ERROR: negative balance allowed")
        return 1
    except InsufficientBalanceError:
        print("negative balance correctly blocked")

    print("wallet validation PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
