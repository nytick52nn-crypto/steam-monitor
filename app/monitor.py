import json
import re
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import AUTO_SCAN_ENABLED, CHECK_INTERVAL_SEC, ITEMS_FILE
from app.database import SessionLocal
from app.history import init_db, save_bulk_snapshots
from app.logger import setup_logging
from app.models import PriceHistory
from app.signals import evaluate_and_notify
from app.steam_api import get_priceoverview

log = setup_logging("monitor")

FALLBACK_ITEMS = [
    {"name": "Fracture Case", "hash_name": "Fracture%20Case", "enabled": True, "priority": 1},
    {"name": "Recoil Case", "hash_name": "Recoil%20Case", "enabled": True, "priority": 1},
    {"name": "Revolution Case", "hash_name": "Revolution%20Case", "enabled": True, "priority": 1},
]

CURRENCY_SUFFIXES = ("\u0440\u0443\u0431.", "p\u0443\u0431.", "\u0440\u0443\u0431", "\u20bd", "$", "\u20ac", "USD", "EUR", "RUB")


def load_items(path: str = ITEMS_FILE) -> list[dict]:
    """Load tracked items from JSON file, filtering enabled and sorting by priority."""
    items_path = Path(path)
    if not items_path.exists():
        log.warning("Items file not found: %s — using %d fallback items", path, len(FALLBACK_ITEMS))
        return list(FALLBACK_ITEMS)

    try:
        with open(items_path, encoding="utf-8") as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read items file %s: %s — using %d fallback items", path, exc, len(FALLBACK_ITEMS))
        return list(FALLBACK_ITEMS)

    if not isinstance(raw, list) or not raw:
        log.warning("Items file %s is empty or not a list — using %d fallback items", path, len(FALLBACK_ITEMS))
        return list(FALLBACK_ITEMS)

    enabled = [item for item in raw if item.get("enabled", True)]
    enabled.sort(key=lambda x: x.get("priority", 999))

    log.info("Loaded %d items from %s (%d total, %d enabled)", len(enabled), path, len(raw), len(enabled))
    return enabled


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


def process_item(item: dict) -> tuple[bool, dict | None]:
    item_name = item["name"]
    hash_name = item.get("hash_name", item_name)
    log.info("Fetching: %s", item_name)
    data = get_priceoverview(hash_name)

    if not data:
        log.warning("No data returned for: %s", item_name)
        return False, None

    lowest_price = data.get("median_price") or data.get("lowest_price")
    if not lowest_price:
        log.warning("No price in response for: %s | data=%s", item_name, data)
        return False, None

    price = (
        float(lowest_price)
        if isinstance(lowest_price, (int, float))
        else parse_price(str(lowest_price))
    )
    if price is None:
        log.warning("Price parse failed for %s: %r", item_name, lowest_price)
        return False, None

    volume = parse_volume(data.get("volume", 0))
    snapshot = {"item_name": item_name, "price": price, "volume": volume}
    saved = save_price(item_name=item_name, price=price, volume=volume)

    if saved:
        median_raw = data.get("median_price")
        median_price = parse_price(median_raw) if median_raw else None
        signal = evaluate_and_notify(
            item_name=item_name,
            current_price=price,
            volume=volume,
            median_price=median_price,
        )
        if signal:
            log.info("Signal for %s: %s", item_name, signal)

    return saved, snapshot


def run_monitor() -> None:
    try:
        init_db()
    except Exception as exc:
        log.error("Price history DB init skipped (monitor continues): %s", exc)

    items = load_items()

    if AUTO_SCAN_ENABLED:
        try:
            from app.scanner import SteamMarketScanner

            scanner = SteamMarketScanner()
            new_items = scanner.scan()
            scanner.update_items_file(ITEMS_FILE, new_items)
            items = load_items(ITEMS_FILE)
            log.info("Items reloaded after scan: %d total", len(items))
        except Exception as e:
            log.exception("Scanner failed but monitor continues: %s", e)

    log.info("Monitor started. Items=%d, interval=%ds", len(items), CHECK_INTERVAL_SEC)

    while True:
        log.info("--- Scan cycle started ---")
        saved = 0
        snapshots: list[dict] = []

        for item in items:
            try:
                ok, snapshot = process_item(item)
                if snapshot:
                    snapshots.append(snapshot)
                if ok:
                    saved += 1
            except Exception as exc:
                log.exception("Unexpected error for %s: %s", item.get("name", item), exc)

        if snapshots:
            try:
                save_bulk_snapshots(snapshots)
            except Exception as exc:
                log.error("Price history bulk save failed (monitor continues): %s", exc)

        log.info("Scan complete: %d/%d items saved", saved, len(items))
        log.info("Sleeping %d seconds...", CHECK_INTERVAL_SEC)
        time.sleep(CHECK_INTERVAL_SEC)
