from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_api_key
from app.api.schemas import DailyBalanceResponse
from app.domain.models import DailyBalance
from app.infra.cache import get_cached_balance, set_cached_balance
from app.infra.db import get_db
from app.infra.repository import DailyBalanceRepository
from app.observability.metrics import cache_hit_total, cache_miss_total

router = APIRouter(prefix="/consolidated", tags=["consolidated"], dependencies=[Depends(require_api_key)])


@router.get("/{for_date}", response_model=DailyBalanceResponse)
def get_consolidated(for_date: date_type, db: Session = Depends(get_db)) -> DailyBalance:
    cached = get_cached_balance(for_date)
    if cached is not None:
        cache_hit_total.inc()
        return cached

    cache_miss_total.inc()
    # Read model is pre-aggregated (ADR 0003): this is a primary-key SELECT, not a scan/join.
    balance = DailyBalanceRepository(db).get(for_date) or DailyBalance.empty(for_date)
    set_cached_balance(balance)
    return balance


@router.get("", response_model=list[DailyBalanceResponse])
def list_consolidated(
    from_: date_type = Query(alias="from"),
    to: date_type = Query(),
    db: Session = Depends(get_db),
) -> list[DailyBalance]:
    return DailyBalanceRepository(db).list_range(start=from_, end=to)
