from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import EntryType


class EntryCreateRequest(BaseModel):
    amount: Decimal = Field(gt=0, description="Must be a positive value; sign is conveyed by `type`.")
    type: EntryType
    description: str = Field(min_length=1, max_length=500)
    occurred_at: datetime | None = Field(
        default=None, description="Defaults to the time the request is received."
    )


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    type: EntryType
    description: str
    occurred_at: datetime
    created_at: datetime


class EntryListResponse(BaseModel):
    items: list[EntryResponse]
    page: int
    page_size: int
    total: int
