# transactions/services/duplicates.py
from transactions.models import Transaction
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

@trace
def find_duplicates(rows):
    for r in rows:
        r["_is_duplicate"] = Transaction.objects.filter(
            date=r.get("date"),
            amount=r.get("amount"),
            description=r.get("description"),
            bank_account=r.get("bank_account"),
        ).exists()
    return rows