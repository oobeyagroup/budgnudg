# transactions/selectors.py
from django.db.models import Count
from transactions.models import Transaction, Category

def recent_transactions(limit=50):
    return Transaction.objects.order_by("-date")[:limit]

def account_summary():
    # build your per-account monthly counts + missing subcategory/payoree counts
    ...