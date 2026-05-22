import random
import time

import requests

from app.config import (
    STEAM_APP_ID,
    STEAM_CURRENCY,
    STEAM_REQUEST_DELAY_MAX,
    STEAM_REQUEST_DELAY_MIN,
)
from app.logger import setup_logging

log = setup_logging("steam_api")

STEAM_PRICE_URL = "https://steamcommunity.com/market/priceoverview/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    "Referer": "https://steamcommunity.com/market/",
}


def get_priceoverview(market_hash_name: str, retries: int = 2) -> dict | None:
    params = {
        "appid": STEAM_APP_ID,
        "currency": STEAM_CURRENCY,
        "market_hash_name": market_hash_name,
    }

    last_error = None

    for attempt in range(1, retries + 2):
        try:
            log.debug(
                "Requesting price for: %s (appid=%s, attempt=%d)",
                market_hash_name,
                STEAM_APP_ID,
                attempt,
            )

            response = requests.get(
                STEAM_PRICE_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
            )

            if response.status_code != 200:
                log.warning(
                    "Steam HTTP %s for %s: %s",
                    response.status_code,
                    market_hash_name,
                    response.text[:200],
                )
                return None

            data = response.json()

            if not data.get("success"):
                log.warning(
                    "Steam API returned success=false for %s: %s",
                    market_hash_name,
                    data,
                )
                return None

            log.info(
                "Price fetched: %s -> lowest=%s median=%s volume=%s",
                market_hash_name,
                data.get("lowest_price"),
                data.get("median_price"),
                data.get("volume"),
            )

            delay = random.uniform(STEAM_REQUEST_DELAY_MIN, STEAM_REQUEST_DELAY_MAX)
            time.sleep(delay)

            return data

        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            log.warning(
                "Steam request failed for %s (attempt %d/%d): %s",
                market_hash_name,
                attempt,
                retries + 1,
                exc,
            )
            if attempt <= retries:
                time.sleep(3 * attempt)

    log.error("Steam request exhausted retries for %s: %s", market_hash_name, last_error)
    return None
