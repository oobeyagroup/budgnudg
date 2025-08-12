# transactions/services/categories.py
import csv
from io import StringIO
import logging
from transactions.models import Category

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = {"Category"}  # SubCategory optional

def import_categories_from_text(text: str) -> dict:
    """
    Parse CSV text and upsert Category/Subcategory rows.
    Returns counts: {'created': int, 'updated': int, 'rows': int}
    """
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_HEADERS - headers
    if missing:
        raise ValueError(f"Missing required header(s): {', '.join(sorted(missing))}")

    rows = list(reader)
    n = len(rows)

    # warn on large files (no f-strings)
    if n > 250:
        logger.warning("Large category import: %d rows", n)

    created = 0
    updated = 0

    for row in rows:
        category_name = (row.get("Category") or "").strip()
        subcategory_name = (row.get("SubCategory") or "").strip()

        if not category_name:
            # Skip empty category rows
            continue

        parent, _pc = Category.objects.get_or_create(name=category_name, parent=None)

        if subcategory_name:
            sub, was_created = Category.objects.get_or_create(name=subcategory_name, parent=parent)
            if was_created:
                created += 1
            else:
                # nothing to update today; placeholder if you add attributes later
                updated += 0
        else:
            # parent-only row; nothing additional to do
            pass

    return {"created": created, "updated": updated, "rows": n}