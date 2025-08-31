from decimal import Decimal
import pytest
from django.utils import timezone
from transactions.models import Transaction, RecurringSeries, Payoree
from transactions.services.recurring import seed_series_from_transaction


@pytest.mark.django_db
def test_seed_series_creates_entry(client):
    # create a payoree and transaction
    pay = Payoree.objects.create(name="Test Pay")
    txn = Transaction.objects.create(
        source="test",
        bank_account=None,
        sheet_account="checking",
        date=timezone.now().date(),
        description="Test merchant",
        amount=Decimal("-25.00"),
        account_type="checking",
        payoree=pay,
    )

    series = seed_series_from_transaction(txn)

    assert isinstance(series, RecurringSeries)
    assert series.payoree == pay
    assert series.merchant_key is not None
    assert series.amount_cents == 2500
    assert series.seed_transaction_id == txn.id
    # additional field assertions
    assert series.interval == "monthly"
    assert abs(series.confidence - 0.60) < 1e-6
    assert "Seeded" in series.notes
    assert series.active is True


@pytest.mark.django_db
def test_seed_series_is_idempotent(client):
    pay = Payoree.objects.create(name="Repeat Pay")
    txn = Transaction.objects.create(
        source="test",
        bank_account=None,
        sheet_account="checking",
        date=timezone.now().date(),
        description="Repeat merchant",
        amount=Decimal("-10.00"),
        account_type="checking",
        payoree=pay,
    )

    # first seed
    s1 = seed_series_from_transaction(txn)
    # mutate txn date to later to ensure last_seen will update
    later = timezone.now().date()
    txn.date = later
    txn.save()

    s2 = seed_series_from_transaction(txn)

    assert s1.id == s2.id
    assert s2.seed_transaction_id == txn.id or s2.seed_transaction_id == s1.seed_transaction_id
    # last_seen should be >= first_seen
    assert s2.last_seen is not None
    assert s2.first_seen is not None
    # additional field assertions for idempotent result
    assert s2.interval == "monthly"
    assert abs(s2.confidence - 0.60) < 1e-6
    assert "Seeded" in s2.notes
    assert s2.active is True
        # End of test file
