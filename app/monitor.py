import re
import time

from sqlalchemy.orm import Session

from app.config import CHECK_INTERVAL_SEC
from app.database import SessionLocal
from app.logger import setup_logging
from app.models import PriceHistory
from app.signals import evaluate_and_notify
from app.steam_api import get_priceoverview

log = setup_logging("monitor")

TEST_ITEMS = [
    "AK-47 | Redline (Field-Tested)",
    "AWP | Asiimov (Battle-Scarred)",
    "Sticker | s1mple | Stockholm 2021",
]

CURRENCY_SUFFIXES = ("руб.", "pуб.", "руб", "₽", "$", "€", "USD", "EUR", "RUB")


def parse_price(price_text: str) -> float | None:
    if not price_text:
        return None

    try:
        cleaned = price_text.strip()
        for suffix in CURRENCY_SUFFIXES:
            cleaned = cleaned.replace(suffix, "")
        cleaned = cleaned.strip().replace("\u00a0", "").replace(" ", "")

        # Russian Steam format: "2993,73" (comma = decimal)
        if cleaned.count(",") == 1 and cleaned.count(".") == 0:
            cleaned = cleaned.replace(",", ".")
        elif cleaned.count(".") > 1 and "," in cleaned:
            # European thousands: 2.993,73
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
        elif cleaned.count(",") > 1:
            cleaned = cleaned.replace(",", "")

        cleaned = re.sub(r"[^\d.]", "", cleaned)
        if not cleaned or cleaned == ".":
            return None

        return float(cleaned)
    except (ValueError, TypeError) as exc:
        log.error("Failed to parse price %r: %s", price_text, exc)
        return None


def parse_volume(volume_text) -> int:
    if volume_text is None:
        return 0
    try:
        return int(str(volume_text).replace(",", "").replace(" ", "").strip() or 0)
    except ValueError:
        return 0


def save_price(item_name: str, price: float, volume: int) -> bool:
    db: Session | None = None
    try:
        db = SessionLocal()
        row = PriceHistory(
            item_name=item_name,
            hash_name=item_name,
            price=price,
            volume=volume,
        )
        db.add(row)
        db.commit()
        log.info("Saved to DB: %s | price=%.2f | volume=%d", item_name, price, volume)
        return True
    except Exception as exc:
        log.exception("Database save failed for %s: %s", item_name, exc)
        if db:
            db.rollback()
        return False
    finally:
        if db:
            db.close()


def process_item(item: str) -> bool:
    log.info("Fetching: %s", item)
    data = get_priceoverview(item)

    if not data:
        log.warning("No data returned for: %s", item)
        return False

    lowest_price = data.get("lowest_price") or data.get("median_price")
    if not lowest_price:
        log.warning("No price in response for: %s | data=%s", item, data)
        return False

    price = parse_price(lowest_price)
    if price is None:
        log.warning("Price parse failed for %s: %r", item, lowest_price)
        return False

    volume = parse_volume(data.get("volume", 0))
    saved = save_price(item_name=item, price=price, volume=volume)

    if saved:
        median_raw = data.get("median_price")
        median_price = parse_price(median_raw) if median_raw else None
        signal = evaluate_and_notify(
            item_name=item,
            current_price=price,
            volume=volume,
            median_price=median_price,
        )
        if signal:
            log.info("Signal for %s: %s", item, signal)

    return saved


def run_monitor() -> None:
    log.info("Monitor started. Items=%d, interval=%ds", len(TEST_ITEMS), CHECK_INTERVAL_SEC)

    while True:
        log.info("--- Scan cycle started ---")
        saved = 0

        for item in TEST_ITEMS:
            try:
                if process_item(item):
                    saved += 1
            except Exception as exc:
                log.exception("Unexpected error for %s: %s", item, exc)

        log.info("Scan complete: %d/%d items saved", saved, len(TEST_ITEMS))
        log.info("Sleeping %d seconds...", CHECK_INTERVAL_SEC)
        time.sleep(CHECK_INTERVAL_SEC)
