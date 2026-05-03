from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceInfo(BaseModel):
    id: str
    name: str
    category: Literal["news", "trend"]
    description: str


class SourceItem(BaseModel):
    source_id: str
    title: str
    url: str
    published_at: datetime | None = None
    summary: str | None = None


class SourcePreviewResponse(BaseModel):
    source_id: str
    fetched_count: int = Field(ge=0)
    items: list[SourceItem]
