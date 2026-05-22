import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import DATABASE_URL

log = logging.getLogger("database")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def migrate_open_positions() -> None:
    """Add new columns to open_positions if they are missing (SQLite safe)."""
    inspector = inspect(engine)
    if "open_positions" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("open_positions")}
    new_columns = {
        "exit_price": "FLOAT",
        "closed_at": "DATETIME",
        "pnl_rub": "FLOAT",
        "pnl_pct": "FLOAT",
    }
    with engine.begin() as conn:
        for col_name, col_type in new_columns.items():
            if col_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE open_positions ADD COLUMN {col_name} {col_type}")
                )
                log.info("Migrated open_positions: added column %s", col_name)
