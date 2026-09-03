from datetime import date, datetime, timezone
from decimal import Decimal

from app.domain.models import ConsolidationStatus, DailyBalance
from app.domain.services import apply_entry


def test_apply_credit_increases_total_credits():
    balance = DailyBalance.empty(date(2026, 1, 1))

    updated = apply_entry(balance, amount=Decimal("100.00"), entry_type="CREDIT")

    assert updated.total_credits == Decimal("100.00")
    assert updated.total_debits == Decimal("0")
    assert updated.entry_count == 1


def test_apply_debit_increases_total_debits():
    balance = DailyBalance.empty(date(2026, 1, 1))

    updated = apply_entry(balance, amount=Decimal("40.00"), entry_type="DEBIT")

    assert updated.total_debits == Decimal("40.00")
    assert updated.balance == Decimal("-40.00")


def test_balance_is_credits_minus_debits_across_multiple_entries():
    balance = DailyBalance.empty(date(2026, 1, 1))
    balance = apply_entry(balance, amount=Decimal("100.00"), entry_type="CREDIT")
    balance = apply_entry(balance, amount=Decimal("30.00"), entry_type="DEBIT")

    assert balance.balance == Decimal("70.00")
    assert balance.entry_count == 2


def test_status_is_partial_for_today_and_consolidated_for_past_days():
    # UTC, matching how DailyBalance.status derives "today" — date.today() is local time and
    # would disagree with it for part of every day in any non-UTC timezone.
    today_balance = DailyBalance.empty(datetime.now(timezone.utc).date())
    past_balance = DailyBalance.empty(date(2020, 1, 1))

    assert today_balance.status == ConsolidationStatus.PARTIAL
    assert past_balance.status == ConsolidationStatus.CONSOLIDATED
