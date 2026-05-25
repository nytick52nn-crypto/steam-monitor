"""Backend helpers (JSON stores, log parsing, pricing)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import DATA_DIR, PRICE_HISTORY_DB
from app.logger import LOG_DIR

WATCHLIST_FILE = DATA_DIR / "watchlist.json"
FILTER_PRESETS_FILE = DATA_DIR / "filter_presets.json"
BACKTEST_HISTORY_FILE = DATA_DIR / "backtest_history.json"

_LOG_LINE_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| (\w+)\s+\| ([^|]+) \| (.*)$"
)


def _read_json_list(path: Path) -> list:
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_json_list(path: Path, data: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_watchlist() -> list[str]:
    return [str(x) for x in _read_json_list(WATCHLIST_FILE)]


def add_to_watchlist(item_name: str) -> list[str]:
    items = get_watchlist()
    name = item_name.strip()
    if name and name not in items:
        items.append(name)
        _write_json_list(WATCHLIST_FILE, items)
    return items


def remove_from_watchlist(item_name: str) -> list[str]:
    name = item_name.strip()
    items = [x for x in get_watchlist() if x != name]
    _write_json_list(WATCHLIST_FILE, items)
    return items


def is_on_watchlist(item_name: str) -> bool:
    return item_name.strip() in get_watchlist()


def get_filter_presets() -> list[dict]:
    return _read_json_list(FILTER_PRESETS_FILE)


def save_filter_preset(name: str, filters: dict) -> dict:
    presets = get_filter_presets()
    preset = {"id": uuid.uuid4().hex[:12], "name": name, "filters": filters}
    presets.append(preset)
    _write_json_list(FILTER_PRESETS_FILE, presets)
    return preset


def delete_filter_preset(preset_id: str) -> bool:
    presets = get_filter_presets()
    new_list = [p for p in presets if p.get("id") != preset_id]
    if len(new_list) == len(presets):
        return False
    _write_json_list(FILTER_PRESETS_FILE, new_list)
    return True


def get_backtest_history() -> list[dict]:
    return _read_json_list(BACKTEST_HISTORY_FILE)


def append_backtest_result(result: dict) -> dict:
    history = get_backtest_history()
    entry = {
        "id": uuid.uuid4().hex[:12],
        "created_at": datetime.now(timezone.utc).isoformat(),
        **result,
    }
    history.insert(0, entry)
    history = history[:50]
    _write_json_list(BACKTEST_HISTORY_FILE, history)
    return entry


def get_latest_price(item_name: str) -> float | None:
    path = Path(PRICE_HISTORY_DB)
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT price FROM price_history
            WHERE item_name = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (item_name,),
        ).fetchone()
        conn.close()
        return float(row["price"]) if row else None
    except Exception:
        return None


def get_last_scan_time() -> str | None:
    log_file = LOG_DIR / "monitor.log"
    if not log_file.is_file():
        return _last_price_history_timestamp()
    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in reversed(lines[-500:]):
            if "--- Scan cycle started ---" in line:
                m = _LOG_LINE_RE.match(line)
                if m:
                    return m.group(1)
        return _last_price_history_timestamp()
    except OSError:
        return _last_price_history_timestamp()


def _last_price_history_timestamp() -> str | None:
    path = Path(PRICE_HISTORY_DB)
    if not path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=5)
        row = conn.execute(
            "SELECT MAX(timestamp) AS ts FROM price_history"
        ).fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


def parse_log_file(
    *,
    level: str | None = None,
    search: str = "",
    limit: int = 200,
    tail: bool = True,
) -> tuple[list[dict], int]:
    log_file = LOG_DIR / "monitor.log"
    if not log_file.is_file():
        return [], 0

    try:
        lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], 0

    entries: list[dict] = []
    level_upper = (level or "").upper()
    search_lower = search.lower()

    for raw in lines:
        m = _LOG_LINE_RE.match(raw)
        if m:
            ts, lvl, logger, msg = m.groups()
        else:
            ts, lvl, logger, msg = "", "INFO", "", raw

        if level_upper and lvl.upper() != level_upper:
            continue
        if search_lower and search_lower not in raw.lower():
            continue

        entries.append(
            {
                "timestamp": ts,
                "level": lvl.strip(),
                "logger": logger.strip(),
                "message": msg.strip(),
                "raw": raw,
            }
        )

    total = len(entries)
    if tail:
        entries = entries[-limit:]
    else:
        entries = entries[:limit]
    return entries, total


def monitor_recently_active(minutes: int = 30) -> bool:
    last = get_last_scan_time()
    if not last:
        return False
    try:
        if "T" in last:
            dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (now - dt).total_seconds() < minutes * 60
    except ValueError:
        return False
