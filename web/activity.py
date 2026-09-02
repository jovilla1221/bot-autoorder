"""Activity log in-memory (ring buffer) untuk health monitor dashboard.

Mencatat event penting: transaksi masuk, akun terjual, error poller,
login dashboard, aksi admin. Tidak persisten — cukup untuk monitor.
"""
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel

Level = Literal["info", "warning", "error"]

_MAX_EVENTS = 200
_events: deque[dict] = deque(maxlen=_MAX_EVENTS)

logger = logging.getLogger(__name__)


class ActivityEvent(BaseModel):
    level: Level
    category: str
    message: str
    timestamp: str


def log_event(level: Level, category: str, message: str) -> None:
    """Catat event ke ring buffer + ke logging standar."""
    event = ActivityEvent(
        level=level,
        category=category,
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    _events.appendleft(event.model_dump())
    log = logger.info if level == "info" else logger.warning if level == "warning" else logger.error
    log("[%s] %s", category, message)


def recent_events(limit: int = 50) -> list[dict]:
    return list(_events)[:limit]
