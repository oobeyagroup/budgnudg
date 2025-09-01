from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone
from transactions.models import Transaction, Payoree, RecurringSeries


@pytest.mark.django_db
def test_create_recurring_from_transaction_view_posts_and_creates(client):
    pay = Payoree.objects.create(name="View Pay")
    txn = Transaction.objects.create(
        source="test",
        bank_account=None,
        sheet_account="checking",
        date=timezone.now().date(),
        description="View Merchant",
        amount=Decimal("-12.50"),
        account_type="checking",
        payoree=pay,
    )

    url = reverse("transactions:recurring_from_txn", args=[txn.id])
    # set referer to allow redirect back (use root which should exist)
    resp = client.post(url, HTTP_REFERER="/", follow=True)

    # should follow redirect and return 200
    assert resp.status_code == 200
    # series created
    series = RecurringSeries.objects.filter(seed_transaction=txn).first()
    assert series is not None
    assert series.payoree == pay
    assert series.amount_cents == 1250

    # message present in next response (messages are stored in session)
    # messages should be present in the followed response context
    messages = list(resp.context.get("messages"))
    assert any("Recurring series created" in str(m) for m in messages)
    # end
