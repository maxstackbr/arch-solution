from decimal import Decimal

import pytest

from app.domain.models import Entry, EntryType, EntryValidationError


def test_create_entry_with_valid_data_succeeds():
    entry = Entry.create(amount=Decimal("150.00"), type=EntryType.CREDIT, description="Venda balcão")

    assert entry.amount == Decimal("150.00")
    assert entry.type == EntryType.CREDIT
    assert entry.id is not None


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-10.00")])
def test_create_entry_rejects_non_positive_amount(amount):
    with pytest.raises(EntryValidationError):
        Entry.create(amount=amount, type=EntryType.DEBIT, description="Pagamento fornecedor")


def test_create_entry_rejects_empty_description():
    with pytest.raises(EntryValidationError):
        Entry.create(amount=Decimal("10.00"), type=EntryType.CREDIT, description="   ")


def test_create_entry_defaults_occurred_at_to_now_when_not_provided():
    entry = Entry.create(amount=Decimal("10.00"), type=EntryType.CREDIT, description="Venda")

    assert entry.occurred_at is not None
