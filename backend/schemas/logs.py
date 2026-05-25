from pydantic import BaseModel, Field


class LogEntry(BaseModel):
    timestamp: str
    level: str
    logger: str
    message: str
    raw: str


class LogsResponse(BaseModel):
    entries: list[LogEntry]
    total: int
    file: str
