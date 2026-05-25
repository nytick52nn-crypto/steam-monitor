from datetime import datetime, timedelta

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import ALERT_COOLDOWN_SEC
from app.database import SessionLocal
from app.logger import setup_logging
from app.models import AlertSent

log = setup_logging("alert_store")


def get_last_alert(item_name: str, db: Session) -> AlertSent | None:
    return (
        db.query(AlertSent)
        .filter(AlertSent.item_name == item_name)
        .order_by(desc(AlertSent.sent_at))
        .first()
    )


def should_send_signal_alert(item_name: str, signal: str) -> bool:
    """Prevent duplicate spam: same item+signal within cooldown, or unchanged signal state."""
    db = SessionLocal()
    try:
        last = get_last_alert(item_name, db)
        if not last:
            return True

        if last.signal == signal:
            age = datetime.utcnow() - last.sent_at
            if age < timedelta(seconds=ALERT_COOLDOWN_SEC):
                log.info(
                    "Skipping duplicate %s for %s (cooldown %ds remaining)",
                    signal,
                    item_name,
                    int(ALERT_COOLDOWN_SEC - age.total_seconds()),
                )
                return False

        return True
    finally:
        db.close()


def record_alert(item_name: str, signal: str, db: Session | None = None) -> None:
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        db.add(AlertSent(item_name=item_name, signal=signal))
        db.commit()
        log.debug("Recorded alert: %s %s", item_name, signal)
    finally:
        if own_session and db:
            db.close()
