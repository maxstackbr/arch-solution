from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.models import ConsolidationStatus


class DailyBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    total_credits: Decimal
    total_debits: Decimal
    balance: Decimal
    entry_count: int
    status: ConsolidationStatus
    last_updated_at: datetime
