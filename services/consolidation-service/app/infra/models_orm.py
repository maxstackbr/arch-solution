from datetime import date as date_
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class DailyBalanceORM(Base):
    __tablename__ = "daily_balances"

    # Column is named `date`, which would shadow the `date` type in its own Mapped[] annotation
    # once the class body finishes executing — imported under an alias to avoid that collision.
    date: Mapped[date_] = mapped_column(primary_key=True)
    total_credits: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_debits: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProcessedEventORM(Base):
    """Idempotency ledger for the event consumer (ADR 0006) — one row per event_id ever applied."""

    __tablename__ = "processed_events"

    event_id: Mapped[str] = mapped_column(primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
