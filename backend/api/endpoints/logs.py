from fastapi import APIRouter, Query

from backend.schemas.logs import LogEntry, LogsResponse
from backend.utils import parse_log_file

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=LogsResponse)
def get_logs(
    level: str | None = Query(None),
    search: str = Query(""),
    limit: int = Query(200, ge=10, le=1000),
) -> LogsResponse:
    entries, total = parse_log_file(level=level, search=search, limit=limit)
    return LogsResponse(
        entries=[LogEntry(**e) for e in entries],
        total=total,
        file="logs/monitor.log",
    )
