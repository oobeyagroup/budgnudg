# transactions/services/suggestions.py
from transactions.categorization import extract_merchant_from_description, categorize_transaction
from transactions.models import LearnedSubcat, LearnedPayoree
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

@trace
def apply_suggestions(rows):
    out = []
    for r in rows:
        desc = r.get("description","") or ""
        key = extract_merchant_from_description(desc)
        if key and not r.get("subcategory"):
            sub = (LearnedSubcat.objects
                   .filter(key=key)
                   .order_by("-count")
                   .values_list("subcategory__name", flat=True)
                   .first())
            if sub:
                r["subcategory"] = sub
            else:
                _, fallback = categorize_transaction(desc, r.get("amount") or 0)
                if fallback:
                    r["subcategory"] = fallback
        # payoree similar…
        out.append(r)
    return out