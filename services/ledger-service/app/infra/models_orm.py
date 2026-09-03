import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infra.db import Base


class EntryORM(Base):
    __tablename__ = "entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    amount: Mapped[str] = mapped_column(Numeric(14, 2))
    type: Mapped[str] = mapped_column(String(6))
    description: Mapped[str] = mapped_column(String(500))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
