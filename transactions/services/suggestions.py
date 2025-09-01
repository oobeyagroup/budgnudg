# transactions/services/suggestions.py
from transactions.categorization import categorize_transaction
from transactions.models import LearnedSubcat
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)


@trace
def apply_suggestions(rows):
    out = []
    for r in rows:
        desc = r.get("description", "") or ""
        # Use description as key for learning lookups (no merchant extraction)
        key = desc.upper().strip()
        if key and not r.get("subcategory"):
            sub = (
                LearnedSubcat.objects.filter(key=key)
                .order_by("-count")
                .values_list("subcategory__name", flat=True)
                .first()
            )
            if sub:
                r["subcategory"] = sub
            else:
                _, fallback = categorize_transaction(desc, r.get("amount") or 0)
                if fallback:
                    r["subcategory"] = fallback
        # payoree similar…
        out.append(r)
    return out
