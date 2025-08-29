# transactions/services/duplicates.py
from transactions.models import Transaction
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)


@trace
def find_duplicates(rows):
    for r in rows:
        bank_account_name = r.get("bank_account")
        filter_kwargs = {
            "date": r.get("date"),
            "amount": r.get("amount"),
            "description": r.get("description"),
        }

        # If bank_account is provided, filter by FinancialAccount name
        if bank_account_name and bank_account_name.strip():
            filter_kwargs["bank_account__name"] = bank_account_name

        r["_is_duplicate"] = Transaction.objects.filter(**filter_kwargs).exists()
    return rows
