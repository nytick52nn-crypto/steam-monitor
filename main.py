import subprocess
import sys
import traceback
from pathlib import Path

from app.config import DATA_DIR, TELEGRAM_STARTUP_TEST, telegram_config_status
from app.logger import setup_logging
from app.telegram_validate import run_telegram_validation

log = setup_logging("main")


def ensure_directories() -> None:
    for folder in (DATA_DIR, Path("charts"), Path("logs")):
        folder.mkdir(parents=True, exist_ok=True)
        log.debug("Directory ready: %s", folder.resolve())


def start_dashboard() -> subprocess.Popen:
    log.info("Starting Streamlit dashboard on :8501")
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "web/dashboard.py",
            "--server.port",
            "8501",
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def main() -> None:
    log.info("Steam monitor starting")

    try:
        ensure_directories()

        from app.database import engine
        from app.models import Base

        Base.metadata.create_all(bind=engine)
        log.info("Database ready at %s", DATA_DIR / "steam_cards.db")

        from app.wallet import init_wallet

        wallet = init_wallet()
        log.info(
            "Virtual wallet ready: balance=%.2f starting=%.2f",
            wallet.balance,
            wallet.starting_balance,
        )

        tg = telegram_config_status()
        log.info(
            "Telegram .env: enabled=%s token=%s chat=%s ready=%s",
            tg["enabled"],
            tg["token_masked"],
            tg["chat_id"],
            tg["ready"],
        )
        if TELEGRAM_STARTUP_TEST:
            run_telegram_validation()

        dashboard = start_dashboard()
        log.info("Dashboard process PID=%s", dashboard.pid)

        from app.monitor import run_monitor

        run_monitor()

    except KeyboardInterrupt:
        log.info("Shutdown requested")
    except Exception as exc:
        log.exception("Fatal error: %s", exc)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
