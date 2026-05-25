import random
import re
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8",
    "Referer": "https://steamcommunity.com/market/",
    "X-Requested-With": "XMLHttpRequest",
}


def get_steam_session() -> requests.Session:
    from app.config import STEAM_LOGIN_SECURE, STEAM_SESSION_COOKIE

    session = requests.Session()
    session.headers.update(HEADERS)
    if STEAM_SESSION_COOKIE and STEAM_LOGIN_SECURE:
        session.cookies.set(
            "sessionid",
            STEAM_SESSION_COOKIE,
            domain="steamcommunity.com",
        )
        session.cookies.set(
            "steamLoginSecure",
            STEAM_LOGIN_SECURE,
            domain="steamcommunity.com",
        )
        log.info("Steam: authenticated session active")
    else:
        log.warning("Steam: anonymous — add cookies to .env to avoid blocks")
    return session


def _parse_price(price_str: str | None) -> float | None:
    """Parse Steam price string to float.
    Handles formats: '135,00 ₽', '1 350,00 ₽', '$1.35', '1.35 USD'
    """
    if not price_str:
        return None
    try:
        # Remove all non-numeric chars except dot and comma
        cleaned = re.sub(r"[^\d.,]", "", price_str.strip())
        if not cleaned:
            return None
        # If both dot and comma present: last one is decimal separator
        if "," in cleaned and "." in cleaned:
            # e.g. "1.350,00" → remove dots, replace comma with dot
            if cleaned.rfind(",") > cleaned.rfind("."):
                cleaned = cleaned.replace(".", "").replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        elif "," in cleaned:
            # e.g. "135,00" → "135.00"
            parts = cleaned.split(",")
            if len(parts) == 2 and len(parts[1]) <= 2:
                cleaned = cleaned.replace(",", ".")
            else:
                cleaned = cleaned.replace(",", "")
        return float(cleaned)
    except (ValueError, AttributeError):
        log.warning("Could not parse price: %r", price_str)
        return None


def _parse_volume(volume_str: str | None) -> int | None:
    """Parse Steam volume string to int. Handles '1,234' or '1 234'."""
    if not volume_str:
        return None
    try:
        cleaned = re.sub(r"[^\d]", "", volume_str.strip())
        return int(cleaned) if cleaned else None
    except (ValueError, AttributeError):
        return None


def get_priceoverview(market_hash_name: str, retries: int = 2) -> dict | None:
    """Fetch price from Steam Market API.
    
    Returns dict with keys:
        lowest_price (float | None)
        median_price (float | None)  
        volume (int | None)
    or None if request failed.
    """
    params = {
        "appid": STEAM_APP_ID,
        "currency": STEAM_CURRENCY,
        "market_hash_name": market_hash_name,
    }
    last_error = None

    for attempt in range(1, retries + 2):
        try:
            log.debug(
                "Requesting price for: %s (appid=%s, currency=%s, attempt=%d)",
                market_hash_name,
                STEAM_APP_ID,
                STEAM_CURRENCY,
                attempt,
            )
            response = get_steam_session().get(
                STEAM_PRICE_URL,
                params=params,
                timeout=30,
            )

            if response.status_code == 429:
                wait = 30 * attempt
                log.warning("Steam rate limit (429) for %s, waiting %ds", market_hash_name, wait)
                time.sleep(wait)
                continue

            if response.status_code != 200:
                log.warning(
                    "Steam HTTP %s for %s: %s",
                    response.status_code,
                    market_hash_name,
                    response.text[:200],
                )
                return None

            data = response.json()
            log.debug("Steam raw response for %s: %s", market_hash_name, data)

            if not data.get("success"):
                log.warning("Steam API success=false for %s: %s", market_hash_name, data)
                return None

            lowest = _parse_price(data.get("lowest_price"))
            median = _parse_price(data.get("median_price"))
            volume = _parse_volume(data.get("volume"))

            log.info(
                "Price fetched: %s -> lowest=%s median=%s volume=%s (raw: %s / %s)",
                market_hash_name,
                f"{lowest:.2f}" if lowest else "None",
                f"{median:.2f}" if median else "None",
                volume,
                data.get("lowest_price_raw") or data.get("lowest_price"),
                data.get("median_price_raw") or data.get("median_price"),
            )

            # Delay between requests to avoid ban
            delay = random.uniform(STEAM_REQUEST_DELAY_MIN, STEAM_REQUEST_DELAY_MAX)
            time.sleep(delay)

            return {
                "lowest_price": lowest,
                "median_price": median,
                "volume": volume,
                "lowest_price_raw": data.get("lowest_price"),
                "median_price_raw": data.get("median_price"),
            }

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