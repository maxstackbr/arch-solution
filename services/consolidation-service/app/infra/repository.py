from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.domain.models import DailyBalance
from app.domain.services import entry_deltas
from app.infra.models_orm import DailyBalanceORM, ProcessedEventORM


class DailyBalanceRepository:
    def __init__(self, session: Session):
        self._session = session

    def get(self, for_date: date) -> DailyBalance | None:
        row = self._session.get(DailyBalanceORM, for_date)
        return _to_domain(row) if row else None

    def list_range(self, *, start: date, end: date) -> list[DailyBalance]:
        stmt = (
            select(DailyBalanceORM)
            .where(DailyBalanceORM.date >= start, DailyBalanceORM.date <= end)
            .order_by(DailyBalanceORM.date)
        )
        rows = self._session.execute(stmt).scalars().all()
        return [_to_domain(row) for row in rows]


class EventProcessor:
    """Applies EntryCreated events to the read model idempotently.

    Each call runs in its own transaction: insert into processed_events first (the
    idempotency check), then upsert daily_balances — both committed together, so a crash
    between the two can never leave the read model updated without the dedup record (or
    vice versa). See docs/adr/0006-consumidor-idempotente.md.
    """

    def __init__(self, session_factory: sessionmaker):
        self._session_factory = session_factory

    def process(self, event: dict) -> bool:
        """Returns True if the event was applied, False if it was a duplicate (already seen)."""
        now = datetime.now(timezone.utc)
        with self._session_factory() as session:
            try:
                session.add(ProcessedEventORM(event_id=event["event_id"], processed_at=now))
                session.flush()
            except IntegrityError:
                session.rollback()
                return False

            occurred_date = date.fromisoformat(event["occurred_date"])
            credit_delta, debit_delta = entry_deltas(
                amount=Decimal(event["amount"]), entry_type=event["type"]
            )
            self._add_to_daily_balance(
                session,
                occurred_date=occurred_date,
                credit_delta=credit_delta,
                debit_delta=debit_delta,
                now=now,
            )

            session.commit()
            return True

    def _add_to_daily_balance(
        self,
        session: Session,
        *,
        occurred_date: date,
        credit_delta: Decimal,
        debit_delta: Decimal,
        now: datetime,
    ) -> None:
        """Applies the deltas as a relative UPDATE, never as a read-modify-write.

        Two workers consuming different events for the same day run concurrently (the worker
        scales on queue depth — see docs/02-target-architecture.md), and under READ COMMITTED
        a SELECT-then-write would let one of them overwrite the other's increment. Letting the
        database do the arithmetic makes the update commutative, so the order the events land
        in never changes the result.
        """
        increments = {
            DailyBalanceORM.total_credits: DailyBalanceORM.total_credits + credit_delta,
            DailyBalanceORM.total_debits: DailyBalanceORM.total_debits + debit_delta,
            DailyBalanceORM.entry_count: DailyBalanceORM.entry_count + 1,
            DailyBalanceORM.last_updated_at: now,
        }
        stmt = update(DailyBalanceORM).where(DailyBalanceORM.date == occurred_date).values(increments)

        if session.execute(stmt).rowcount:
            return

        # First event of the day: create the row. A concurrent worker may win the race and
        # insert it first, in which case the savepoint rolls back and the UPDATE above is
        # retried against the row that now exists.
        try:
            with session.begin_nested():
                session.execute(
                    insert(DailyBalanceORM).values(
                        date=occurred_date,
                        total_credits=credit_delta,
                        total_debits=debit_delta,
                        entry_count=1,
                        last_updated_at=now,
                    )
                )
        except IntegrityError:
            session.execute(stmt)


def _to_domain(row: DailyBalanceORM) -> DailyBalance:
    last_updated_at = row.last_updated_at
    if last_updated_at.tzinfo is None:
        last_updated_at = last_updated_at.replace(tzinfo=timezone.utc)
    return DailyBalance(
        date=row.date,
        total_credits=row.total_credits,
        total_debits=row.total_debits,
        entry_count=row.entry_count,
        last_updated_at=last_updated_at,
    )
