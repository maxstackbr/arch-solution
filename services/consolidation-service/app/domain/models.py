from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum


class ConsolidationStatus(str, Enum):
    PARTIAL = "PARTIAL"
    CONSOLIDATED = "CONSOLIDATED"


@dataclass(frozen=True)
class DailyBalance:
    """Read model materialized from EntryCreated events (see docs/adr/0003-read-model-materializado.md).
    Never written to directly by an external client — only by the event consumer."""

    date: date
    total_credits: Decimal
    total_debits: Decimal
    entry_count: int
    last_updated_at: datetime

    @property
    def balance(self) -> Decimal:
        return self.total_credits - self.total_debits

    @property
    def status(self) -> ConsolidationStatus:
        # occurred_date is always derived from occurred_at in UTC (see docs/03-api-contracts.md),
        # so "today" must be computed in UTC too — comparing against local server time would
        # misclassify PARTIAL/CONSOLIDATED near midnight in non-UTC timezones.
        today_utc = datetime.now(timezone.utc).date()
        return ConsolidationStatus.PARTIAL if self.date == today_utc else ConsolidationStatus.CONSOLIDATED

    @classmethod
    def empty(cls, for_date: date) -> "DailyBalance":
        return cls(
            date=for_date,
            total_credits=Decimal("0"),
            total_debits=Decimal("0"),
            entry_count=0,
            last_updated_at=datetime.now(timezone.utc),
        )
