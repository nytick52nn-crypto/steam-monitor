from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    message: str
    ok: bool = True


class PaginatedMeta(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
