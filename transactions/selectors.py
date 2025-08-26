# transactions/selectors.py
from django.db.models import Count, Q, F  # Q = complex logical conditions; F = refer to fields in expressions, not just static values.
from transactions.models import Transaction, Category
import re
def recent_transactions(limit=50):
    return Transaction.objects.order_by("-date")[:limit]

def account_summary():
    # build your per-account monthly counts + missing subcategory/payoree counts
    ...

CHECK_RE = re.compile(r"\bCHECK\s*(\d{3,6})\b", re.IGNORECASE)

def extract_check_number_from_description(desc: str) -> int | None:
    if not desc:
        return None
    m = CHECK_RE.search(desc)
    return int(m.group(1)) if m else None

def check_like_transactions(account: str | None = None, start=None, end=None):
    qs = Transaction.objects.filter(description__iregex=r'\bCHECK\s*\d+')
    if account:
        qs = qs.filter(bank_account=account)
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    return qs.select_related("payoree", "subcategory").order_by("-date")