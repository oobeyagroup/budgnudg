# Development Notes – budgnudg

## Overview
This file captures the **final agreed-upon code and architecture decisions** from the development chat, with all debugging noise removed. It’s meant as a quick reference for correct, working code and patterns.

---

## 1. Import & Mapping Pipeline

### Models

#### ImportBatch
- Holds metadata for an uploaded CSV.
- Related to `ImportRow` via `rows` reverse relation.
- Tracks status (`uploaded`, `previewed`, `committing`, `committed`).
- Linked to a `MappingProfile` after preview.

#### ImportRow
- Stores:
  - `raw` (JSON of original CSV row)
  - `parsed` (JSON of mapped row with `_date`, `_amount`, `_suggestions`, `_errors`)
  - Normalized fields: `norm_date`, `norm_amount`, `norm_description`
  - Flags: `is_duplicate`
  - `errors` (list of strings)
  - Optional `committed_txn_id` foreign key to final `Transaction`

---

## 2. Mapping Service

### Final `apply_profile_to_batch`

```python
from decimal import Decimal
from typing import Tuple
from django.db import transaction as dbtx
from .models import ImportBatch
from transactions.services.helpers import is_duplicate
from transactions.categorization import suggest_subcategory
import datetime
import logging

logger = logging.getLogger(__name__)

def _json_safe(v):
    """Convert datatypes to JSON-safe values."""
    import datetime as dt
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    return v

def apply_profile_to_batch(batch: ImportBatch, profile, bank_account_hint: str = "") -> Tuple[int, int]:
    """
    Map all rows in a batch using the selected MappingProfile.
    Persists parsed dict + denormalized norm_* fields + errors + duplicate flag.
    Returns (updated_count, dup_count).
    """
    assert batch is not None, "batch is required"
    mapping = getattr(profile, "column_map", None)
    if not isinstance(mapping, dict):
        raise TypeError(f"MappingProfile.column_map must be dict; got {type(mapping)}")

    updated = 0
    dup_count = 0

    with dbtx.atomic():
        for row in batch.rows.order_by("row_index").all():
            try:
                out = map_row_with_profile(row.raw, profile)  # produces _date, _amount, _suggestions, _errors
            except Exception as e:
                errs = list(row.errors or [])
                errs.append(f"map: {e}")
                row.errors = errs
                row.save(update_fields=["errors"])
                logger.warning("Mapping error on row %s in batch %s", row.row_index, batch.pk, exc_info=True)
                continue

            # JSON-safe storage
            json_safe_out = {k: _json_safe(v) for k, v in out.items()}

            row.parsed = json_safe_out
            row.norm_date = out.get("_date") or None
            amt = out.get("_amount")
            row.norm_amount = Decimal(amt) if isinstance(amt, (int, float, Decimal)) else None
            row.norm_description = out.get("description") or ""
            row.suggestions = out.get("_suggestions") or {}
            row.errors = out.get("_errors") or []

            # Duplicate flag
            dup_payload = {
                "date": row.norm_date,
                "amount": row.norm_amount,
                "description": row.norm_description,
                "bank_account": bank_account_hint or "",
            }
            row.is_duplicate = bool(is_duplicate(dup_payload))
            if row.is_duplicate:
                dup_count += 1

            row.save(update_fields=[
                "parsed", "norm_date", "norm_amount", "norm_description",
                "suggestions", "errors", "is_duplicate"
            ])
            updated += 1

        batch.profile = profile
        batch.status = "previewed"
        batch.save(update_fields=["profile", "status"])

    return updated, dup_count