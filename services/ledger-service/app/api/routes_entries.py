import logging
from datetime import date as date_type
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.api.schemas import EntryCreateRequest, EntryListResponse, EntryResponse
from app.domain.models import Entry, EntryValidationError
from app.infra.db import get_db
from app.infra.event_publisher import publisher
from app.infra.repository import EntryRepository

logger = logging.getLogger("ledger.entries")

router = APIRouter(prefix="/entries", tags=["entries"], dependencies=[Depends(require_api_key)])


@router.post("", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(payload: EntryCreateRequest, db: Session = Depends(get_db)) -> Entry:
    try:
        entry = Entry.create(
            amount=payload.amount,
            type=payload.type,
            description=payload.description,
            occurred_at=payload.occurred_at,
        )
    except EntryValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    EntryRepository(db).add(entry)
    # Carries the request_id injected by the correlation middleware; entry_id is what ties this
    # line to the consolidation worker's log for the same lançamento (docs/04-observability.md).
    logger.info("entry_created", extra={"entry_id": str(entry.id)})

    # Fire-and-forget: publish failures are logged/metriced but never affect this response (RNF-1, ADR 0005).
    publisher.publish_entry_created(entry)

    return entry


@router.get("", response_model=EntryListResponse)
def list_entries(
    date: date_type | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> EntryListResponse:
    items, total = EntryRepository(db).list(occurred_date=date, page=page, page_size=page_size)
    return EntryListResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: str, db: Session = Depends(get_db)) -> Entry:
    try:
        parsed_id = UUID(entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid id") from exc

    entry = EntryRepository(db).get(parsed_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return entry
