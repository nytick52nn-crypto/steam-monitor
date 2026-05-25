"""Dedicated SQLite price snapshot store for analytics and trend detection."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from queue import Empty, Queue

from app.config import PRICE_HISTORY_DB, PRICE_HISTORY_RETENTION_DAYS
from app.logger import setup_logging

log = setup_logging("history")

_MAX_RETRIES = 5
_RETRY_BASE_DELAY = 0.05

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    price REAL NOT NULL,
    volume INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_price_history_item_ts
ON price_history (item_name, timestamp)
"""

_init_lock = threading.RLock()
_db_ready = False
_worker_thread: threading.Thread | None = None
_write_queue: Queue | None = None
_last_cleanup = 0.0
_CLEANUP_INTERVAL_SEC = 3600


def _db_path() -> Path:
    return Path(PRICE_HISTORY_DB)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _retry_db(operation: str, fn):
    """Run fn(conn); retry on database locked errors."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        conn: sqlite3.Connection | None = None
        try:
            conn = _connect()
            result = fn(conn)
            conn.commit()
            return result
        except sqlite3.OperationalError as exc:
            last_exc = exc
            if conn:
                conn.rollback()
            if "locked" in str(exc).lower() and attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.warning(
                    "Price history DB locked during %s (attempt %d/%d), retry in %.2fs",
                    operation,
                    attempt,
                    _MAX_RETRIES,
                    delay,
                )
                time.sleep(delay)
                continue
            log.error("Price history DB error during %s: %s", operation, exc)
            raise
        except Exception as exc:
            if conn:
                conn.rollback()
            log.error("Price history DB failure during %s: %s", operation, exc)
            raise
        finally:
            if conn:
                conn.close()
    if last_exc:
        raise last_exc
    return None


def init_db() -> bool:
    """Create schema and indexes. Safe to call multiple times."""
    global _db_ready
    with _init_lock:
        if _db_ready:
            return True
        try:

            def _setup(conn: sqlite3.Connection):
                conn.execute(_CREATE_TABLE)
                conn.execute(_CREATE_INDEX)

            _retry_db("init_db", _setup)
            _db_ready = True
            log.info("Price history DB ready: %s", _db_path())
            return True
        except Exception as exc:
            log.error("Price history DB init failed: %s", exc)
            return False


def _insert_snapshots(conn: sqlite3.Connection, items: list[dict]) -> int:
    rows = [
        (
            item["item_name"],
            float(item["price"]),
            item.get("volume"),
        )
        for item in items
        if item.get("item_name") is not None and item.get("price") is not None
    ]
    if not rows:
        return 0
    conn.executemany(
        "INSERT INTO price_history (item_name, price, volume) VALUES (?, ?, ?)",
        rows,
    )
    return len(rows)


def save_snapshot(item_name: str, price: float, volume: int | None = None) -> None:
    """Queue a single snapshot write (non-blocking, never raises)."""
    save_bulk_snapshots(
        [{"item_name": item_name, "price": price, "volume": volume}]
    )


def save_bulk_snapshots(items: list[dict]) -> None:
    """Queue batch insert (non-blocking, never raises)."""
    if not items:
        return
    _ensure_worker()
    try:
        _write_queue.put_nowait(list(items))
    except Exception as exc:
        log.error("Failed to queue price history snapshots: %s", exc)


def cleanup_old_history(days: int | None = None) -> int:
    """Delete snapshots older than retention period. Returns rows deleted."""
    retention = days if days is not None else PRICE_HISTORY_RETENTION_DAYS
    if retention <= 0:
        return 0

    def _cleanup(conn: sqlite3.Connection) -> int:
        cur = conn.execute(
            "DELETE FROM price_history WHERE timestamp < datetime('now', ?)",
            (f"-{int(retention)} days",),
        )
        return cur.rowcount

    try:
        deleted = _retry_db("cleanup_old_history", _cleanup) or 0
        if deleted:
            log.info(
                "Price history cleanup: removed %d rows older than %d days",
                deleted,
                retention,
            )
        return deleted
    except Exception as exc:
        log.error("Price history cleanup failed: %s", exc)
        return 0


def _maybe_scheduled_cleanup() -> None:
    global _last_cleanup
    now = time.time()
    if now - _last_cleanup < _CLEANUP_INTERVAL_SEC:
        return
    _last_cleanup = now
    try:
        cleanup_old_history()
    except Exception as exc:
        log.error("Scheduled price history cleanup failed: %s", exc)


def _worker_loop() -> None:
    while True:
        try:
            batch = _write_queue.get(timeout=1.0)
        except Empty:
            continue
        if batch is None:
            break
        try:
            if not _db_ready and not init_db():
                continue

            def _bulk(conn: sqlite3.Connection) -> int:
                return _insert_snapshots(conn, batch)

            count = _retry_db("save_bulk_snapshots", _bulk) or 0
            log.debug("Price history: saved %d snapshots", count)
        except Exception as exc:
            log.error("Price history worker failed to save %d snapshots: %s", len(batch), exc)
        finally:
            _write_queue.task_done()
            _maybe_scheduled_cleanup()


def _ensure_worker() -> None:
    global _worker_thread, _write_queue
    if _worker_thread is not None and _worker_thread.is_alive():
        return
    with _init_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        init_db()
        _write_queue = Queue(maxsize=500)
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="price-history-writer",
            daemon=True,
        )
        _worker_thread.start()
