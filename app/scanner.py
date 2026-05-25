"""Steam Market auto-scanner — discovers liquid CS2 skins via search API."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

from app.config import (
    AUTO_SCAN_INTERVAL_HOURS,
    DATA_DIR,
    MAX_PRICE_RUB,
    MIN_PRICE_RUB,
    MIN_VOLUME_PER_DAY,
    SCANNER_REQUEST_DELAY,
    SCAN_TOTAL_ITEMS,
    STEAM_APP_ID,
    STEAM_CURRENCY,
)
from app.logger import setup_logging
from app.steam_api import get_steam_session

log = setup_logging("scanner")

SEARCH_URL = "https://steamcommunity.com/market/search/render/"

SCAN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Referer": "https://steamcommunity.com/market/",
}

MAX_RETRIES = 3
PAGE_SIZE = 10
LAST_SCAN_FILE = DATA_DIR / ".scanner_last_run"

_KNIFE_MARKERS = (
    "★",
    "knife",
    "karambit",
    "bayonet",
    "butterfly",
    "m9 bayonet",
    "talon",
    "ursus",
    "nomad knife",
    "skeleton knife",
    "survival knife",
    "paracord knife",
    "classic knife",
    "stiletto",
    "huntsman knife",
    "flip knife",
    "gut knife",
    "falchion",
    "bowie knife",
    "shadow daggers",
    "navaja",
    "stiletto knife",
)

_BLACKLIST_KEYWORDS = (
    "souvenir",
    "capsule",
    "graffiti",
    "music kit",
    " case",
    " case ",
    " agent",
    "patch",
    "nametag",
    " case key",
    " key",
    "operation pass",
    "pin |",
    "collectible",
    "storage unit",
    "tool ",
    "sticker |",
    "autograph capsule",
    "slab",
)


def is_valid_cs2_item(name: str) -> bool:
    """Return True for liquid weapon skins, gloves, and knives; filter junk items."""
    if not name or not name.strip():
        return False

    lower = name.lower()
    for keyword in _BLACKLIST_KEYWORDS:
        if keyword in lower:
            return False

    if lower.endswith(" case") or lower.endswith(" case key"):
        return False

    if "|" in name:
        return True
    if "gloves" in lower:
        return True
    for marker in _KNIFE_MARKERS:
        if marker in lower:
            return True
    return False


def _encode_hash_name(market_hash_name: str) -> str:
    return quote(market_hash_name, safe="")


def _parse_search_price(sell_price: int | None) -> float | None:
    """Steam search sell_price is in minor units (kopecks for RUB)."""
    if sell_price is None:
        return None
    try:
        return float(sell_price) / 100.0
    except (TypeError, ValueError):
        return None


class SteamMarketScanner:
    """Limited Steam Market search scanner with filtering and safe items.json updates."""

    def __init__(self) -> None:
        self._session = get_steam_session()
        self._stats = {
            "scanned": 0,
            "filtered": 0,
            "discovered": 0,
            "duplicates": 0,
            "failures": 0,
        }
        self._start_time = 0.0

    def should_run(self) -> bool:
        """Skip scan if last successful run was within AUTO_SCAN_INTERVAL_HOURS."""
        if not LAST_SCAN_FILE.exists():
            return True
        try:
            last_run = float(LAST_SCAN_FILE.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return True
        elapsed_hours = (time.time() - last_run) / 3600.0
        if elapsed_hours < AUTO_SCAN_INTERVAL_HOURS:
            log.info(
                "Scanner skipped: last run %.1fh ago (interval=%dh)",
                elapsed_hours,
                AUTO_SCAN_INTERVAL_HOURS,
            )
            return False
        return True

    def _mark_scan_complete(self) -> None:
        try:
            LAST_SCAN_FILE.parent.mkdir(parents=True, exist_ok=True)
            LAST_SCAN_FILE.write_text(str(time.time()), encoding="utf-8")
        except OSError as exc:
            log.warning("Could not write scanner timestamp: %s", exc)

    def _request_search(self, start: int, count: int) -> dict | None:
        params = {
            "query": "",
            "start": start,
            "count": count,
            "search_descriptions": 0,
            "sort_column": "quantity",
            "sort_dir": "desc",
            "appid": STEAM_APP_ID,
            "norender": 1,
            "currency": STEAM_CURRENCY,
        }
        headers = {**self._session.headers, **SCAN_HEADERS}
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = self._session.get(
                    SEARCH_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )

                if response.status_code == 429:
                    wait = SCANNER_REQUEST_DELAY * (2 ** (attempt - 1))
                    log.warning(
                        "Scanner rate limit (429), waiting %.0fs (attempt %d/%d)",
                        wait,
                        attempt,
                        MAX_RETRIES,
                    )
                    time.sleep(wait)
                    continue

                if response.status_code != 200:
                    log.warning(
                        "Scanner HTTP %s (start=%d): %s",
                        response.status_code,
                        start,
                        response.text[:200],
                    )
                    self._stats["failures"] += 1
                    return None

                data = response.json()
                if not data.get("success"):
                    log.warning("Scanner success=false (start=%d): %s", start, str(data)[:200])
                    self._stats["failures"] += 1
                    return None

                return data

            except requests.RequestException as exc:
                last_error = exc
                wait = SCANNER_REQUEST_DELAY * (2 ** (attempt - 1))
                log.warning(
                    "Scanner network error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES,
                    exc,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(wait)

        log.error("Scanner request failed after retries (start=%d): %s", start, last_error)
        self._stats["failures"] += 1
        return None

    def _passes_filters(self, name: str, price_rub: float | None, volume: int) -> bool:
        if not is_valid_cs2_item(name):
            return False
        if price_rub is None:
            return False
        if price_rub < MIN_PRICE_RUB or price_rub > MAX_PRICE_RUB:
            return False
        if volume < MIN_VOLUME_PER_DAY:
            return False
        return True

    def _result_to_item(self, row: dict) -> dict | None:
        name = (row.get("hash_name") or row.get("name") or "").strip()
        if not name:
            return None

        price_rub = _parse_search_price(row.get("sell_price"))
        volume = int(row.get("sell_listings") or 0)
        if volume <= 0:
            vol_text = row.get("volume") or row.get("sell_listings_text") or ""
            if vol_text:
                cleaned = re.sub(r"[^\d]", "", str(vol_text))
                volume = int(cleaned) if cleaned else 0

        if not self._passes_filters(name, price_rub, volume):
            return None

        return {
            "name": name,
            "hash_name": _encode_hash_name(name),
            "enabled": True,
            "priority": 5,
            "source": "scanner",
        }

    def scan(self) -> list[dict]:
        """Fetch up to SCAN_TOTAL_ITEMS popular listings; return new item dicts."""
        self._start_time = time.time()
        self._stats = {
            "scanned": 0,
            "filtered": 0,
            "discovered": 0,
            "duplicates": 0,
            "failures": 0,
        }

        if not self.should_run():
            return []

        log.info(
            "Scanner started: target=%d items, price=%.0f–%.0f RUB, min_volume=%d",
            SCAN_TOTAL_ITEMS,
            MIN_PRICE_RUB,
            MAX_PRICE_RUB,
            MIN_VOLUME_PER_DAY,
        )

        seen_hashes: set[str] = set()
        discovered: list[dict] = []
        start = 0

        while len(discovered) < SCAN_TOTAL_ITEMS:
            remaining = SCAN_TOTAL_ITEMS - len(discovered)
            count = PAGE_SIZE
            log.info("Scanner page: start=%d count=%d", start, count)

            data = self._request_search(start=start, count=count)
            time.sleep(SCANNER_REQUEST_DELAY)

            if not data:
                break

            results = data.get("results") or []
            if not results:
                log.info("Scanner: no more results at start=%d", start)
                break

            for row in results:
                self._stats["scanned"] += 1
                name = (row.get("hash_name") or row.get("name") or "").strip()
                price_rub = _parse_search_price(row.get("sell_price"))
                volume = int(row.get("sell_listings") or 0)

                item = self._result_to_item(row)
                if item is None:
                    self._stats["filtered"] += 1
                    log.debug(
                        "Filtered: %s (price=%s volume=%d)",
                        name,
                        f"{price_rub:.2f}" if price_rub else "n/a",
                        volume,
                    )
                    continue

                key = item["hash_name"].lower()
                if key in seen_hashes:
                    self._stats["duplicates"] += 1
                    continue
                seen_hashes.add(key)
                discovered.append(item)
                self._stats["discovered"] += 1
                log.info("Discovered: %s", item["name"])

                if len(discovered) >= SCAN_TOTAL_ITEMS:
                    break

            start += len(results)
            total = int(data.get("total_count") or 0)
            if start >= total or start >= SCAN_TOTAL_ITEMS * 3:
                break

        self._mark_scan_complete()
        self._log_stats()
        return discovered

    def _log_stats(self) -> None:
        duration = time.time() - self._start_time
        log.info(
            "Scanner finished: scanned=%d filtered=%d discovered=%d "
            "duplicates_skipped=%d failures=%d duration=%.1fs",
            self._stats["scanned"],
            self._stats["filtered"],
            self._stats["discovered"],
            self._stats["duplicates"],
            self._stats["failures"],
            duration,
        )

    @staticmethod
    def update_items_file(path: str, new_items: list[dict]) -> int:
        """Merge new_items into items.json without removing existing entries."""
        items_path = Path(path)
        existing: list[dict] = []

        if items_path.exists():
            try:
                with open(items_path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    existing = raw
            except (json.JSONDecodeError, OSError) as exc:
                log.error("Cannot read %s: %s — aborting update", path, exc)
                return 0

        existing_keys = {
            (item.get("hash_name") or _encode_hash_name(item.get("name", ""))).lower()
            for item in existing
            if item.get("name") or item.get("hash_name")
        }

        merged_count = 0
        for item in new_items:
            key = (item.get("hash_name") or "").lower()
            if not key or key in existing_keys:
                continue
            existing.append(item)
            existing_keys.add(key)
            merged_count += 1

        if merged_count == 0:
            log.info("Scanner: no new items to append to %s", path)
            return 0

        payload = json.dumps(existing, ensure_ascii=False, indent=2)
        try:
            json.loads(payload)
        except json.JSONDecodeError as exc:
            log.error("Scanner: merged JSON invalid — aborting write: %s", exc)
            return 0

        tmp_path = items_path.with_suffix(".json.tmp")
        try:
            items_path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(payload + "\n", encoding="utf-8")
            tmp_path.replace(items_path)
        except OSError as exc:
            log.error("Scanner: atomic write failed for %s: %s", path, exc)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            return 0

        log.info(
            "Scanner updated %s: appended %d items (total=%d)",
            path,
            merged_count,
            len(existing),
        )
        return merged_count
