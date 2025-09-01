from datetime import datetime
import json
from decimal import Decimal
from pathlib import Path
import logging
import functools

logger = logging.getLogger(__name__)


def trace(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.debug("TRACE: Called %s.%s", func.__module__, func.__qualname__)
        return func(*args, **kwargs)

    return wrapper


@trace
def parse_transaction_row(row, mapping, bank_account):
    txn_data = {
        "bank_account": bank_account,
        "suggested_subcategory": None,
        "suggested_category": None,
    }

    for csv_col, model_field in mapping.items():
        value = (row.get(csv_col) or "").strip()
        if model_field == "date":
            txn_data["date"] = parse_date(value)
        elif model_field == "amount":
            try:
                txn_data["amount"] = float(Decimal(value))
            except (ValueError, Decimal.InvalidOperation):
                txn_data["amount"] = 0.0
        elif model_field == "subcategory":
            txn_data["subcategory_name"] = value  # Just display in preview
        elif model_field == "payoree":
            txn_data["payoree_name"] = value  # Display only
        else:
            txn_data[model_field] = value

    return txn_data


@trace
def parse_date(value):
    date_formats = ["%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"]
    for fmt in date_formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def normalize_description(desc):
    """
    Normalize transaction descriptions for comparison and similarity matching.
    Removes common variable elements like transaction IDs and web identifiers.
    """
    import re

    # Remove 11-digit numbers and WEB ID numbers
    cleaned = re.sub(r"\b\d{11}\b", "", desc)
    cleaned = re.sub(r"WEB ID[:]? \d+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.lower().strip()


@trace
def read_uploaded_file(uploaded_file, encoding="utf-8-sig"):
    """
    Safely read uploaded file content, handling BOM and decoding.
    Returns decoded string.
    """
    return uploaded_file.read().decode(encoding)


@trace
def get_payoree_name_for_transaction(transaction) -> str:
    """
    Get the payoree name for a transaction.
    This replaces the old merchant_key functionality.
    """
    from .models import Transaction

    if not isinstance(transaction, Transaction):
        return ""

    if transaction.payoree:
        return transaction.payoree.name
    else:
        # Fallback to transaction description if no payoree is set
        return transaction.description or ""
