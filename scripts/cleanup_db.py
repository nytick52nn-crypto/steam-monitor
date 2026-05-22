import sqlite3
from pathlib import Path

DB = Path("data/steam_cards.db")

conn = sqlite3.connect(DB)
deleted_high = conn.execute("DELETE FROM price_history WHERE price >= 100000").rowcount
deleted_sticker = conn.execute(
    "DELETE FROM price_history WHERE item_name LIKE 'Sticker%' AND price > 100"
).rowcount
conn.commit()
remaining = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
print(f"Deleted high prices: {deleted_high}")
print(f"Deleted bad stickers: {deleted_sticker}")
print(f"Remaining records: {remaining}")
