from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.models import Entry, EntryType
from app.infra.models_orm import EntryORM


class EntryRepository:
    def __init__(self, session: Session):
        self._session = session

    def add(self, entry: Entry) -> None:
        self._session.add(
            EntryORM(
                id=entry.id,
                amount=entry.amount,
                type=entry.type.value,
                description=entry.description,
                occurred_at=entry.occurred_at,
                created_at=entry.created_at,
            )
        )
        self._session.commit()

    def get(self, entry_id: UUID) -> Entry | None:
        row = self._session.get(EntryORM, entry_id)
        return _to_domain(row) if row else None

    def list(
        self, *, occurred_date: date | None, page: int, page_size: int
    ) -> tuple[list[Entry], int]:
        stmt = select(EntryORM)
        count_stmt = select(func.count()).select_from(EntryORM)
        if occurred_date is not None:
            stmt = stmt.where(func.date(EntryORM.occurred_at) == occurred_date)
            count_stmt = count_stmt.where(func.date(EntryORM.occurred_at) == occurred_date)

        total = self._session.execute(count_stmt).scalar_one()
        rows = (
            self._session.execute(
                stmt.order_by(EntryORM.occurred_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            .scalars()
            .all()
        )
        return [_to_domain(row) for row in rows], total


def _to_domain(row: EntryORM) -> Entry:
    occurred_at = row.occurred_at
    if occurred_at.tzinfo is None:
        occurred_at = occurred_at.replace(tzinfo=timezone.utc)
    created_at = row.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return Entry(
        id=row.id,
        amount=row.amount,
        type=EntryType(row.type),
        description=row.description,
        occurred_at=occurred_at,
        created_at=created_at,
    )
