# transactions/services/payorees.py
import csv
from io import StringIO
import logging
from transactions.models import Payoree

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = {"Name"}


def import_payorees_from_text(text: str) -> dict:
    """
    Parse CSV text and create Payoree rows.
    Returns counts: {'created': int, 'skipped': int, 'rows': int}
    """
    reader = csv.DictReader(StringIO(text))
    headers = set(reader.fieldnames or [])
    missing = REQUIRED_HEADERS - headers
    if missing:
        raise ValueError(f"Missing required header(s): {', '.join(sorted(missing))}")

    rows = list(reader)
    n = len(rows)

    # warn on large files
    if n > 250:
        logger.warning("Large payoree import: %d rows", n)

    created = 0
    skipped = 0

    for row in rows:
        payoree_name = (row.get("Name") or "").strip()

        if not payoree_name:
            # Skip empty name rows
            skipped += 1
            continue

        payoree, was_created = Payoree.objects.get_or_create(name=payoree_name)
        if was_created:
            created += 1
        else:
            skipped += 1

    return {"created": created, "skipped": skipped, "rows": n}
