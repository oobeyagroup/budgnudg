import pytest
from django.urls import reverse
from transactions.models import Transaction

@pytest.mark.django_db
def test_transaction_list_view_renders(client):
    Transaction.objects.create(date="2025-07-11", description="Hello", amount=1.23, bank_account="CHK")
    resp = client.get(reverse("transactions_list"))
    assert resp.status_code == 200
    assert b"All Transactions" in resp.content