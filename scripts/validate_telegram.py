"""Run Telegram validation outside the monitor loop."""

import sys

from app.telegram_validate import run_telegram_validation

if __name__ == "__main__":
    ok = run_telegram_validation()
    sys.exit(0 if ok else 1)
