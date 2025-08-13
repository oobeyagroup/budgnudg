import datetime as dt
from decimal import Decimal, InvalidOperation
from ingest.models import MappingProfile, ImportBatch, ImportRow
from django.db import transaction as dbtx
import logging
from typing import Tuple, List
# from .utils import parse_date

from transactions.categorization import suggest_subcategory  # your existing function
from transactions.models import Transaction, Category, Payoree
from transactions.services.helpers import is_duplicate  # your existing duplicate checker
from transactions.utils import trace

logger = logging.getLogger(__name__)

def _parse_date(s: str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    raise ValueError(f"Unrecognized date: {s!r}")

def map_row_with_profile(raw_row: dict, profile: MappingProfile):
    mapping = profile.column_map
    out, errors = {}, []
    for csv_col, model_field in mapping.items():
        raw = raw_row.get(csv_col) or ""
        if not isinstance(raw, str):
            raw = str(raw)
        raw = raw.strip()
        if model_field == "date":
            out["date"] = raw
            try: out["_date"] = _parse_date(raw)
            except Exception as e: errors.append(f"date: {e}")
        elif model_field == "amount":
            out["amount"] = raw
            try: out["_amount"] = Decimal(raw.replace(",",""))
            except (InvalidOperation, AttributeError) as e: errors.append(f"amount: {e}")
        else:
            out[model_field] = raw
    desc = out.get("description","")
    sub = suggest_subcategory(desc) or ""
    out["_suggestions"] = {"subcategory": sub} if sub else {}
    out["_errors"] = errors
    return out

def preview_batch(batch: ImportBatch):
    if not batch.profile:
        raise ValueError("Batch has no MappingProfile assigned.")
    rows = []
    for r in batch.rows.order_by("row_index").iterator():
        mapped = map_row_with_profile(r.raw, batch.profile)
        r.norm_description = mapped.get("description","")
        r.norm_date = mapped.get("_date")
        r.norm_amount = mapped.get("_amount")
        r.suggestions = mapped.get("_suggestions",{})
        r.is_duplicate = False  # you can plug your duplicate check here
        r.errors = mapped.get("_errors",[])
        rows.append(r)
    ImportRow.objects.bulk_update(rows, ["norm_description","norm_date","norm_amount","suggestions","is_duplicate","errors"], batch_size=1000)
    batch.status = "previewed"
    batch.save(update_fields=["status"])

@trace
def _json_safe(v):
    """Make values safe for JSONField storage."""
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v

@trace
def apply_profile_to_batch(
    batch: ImportBatch,
    profile,
    bank_account_hint: str | None = None,
) -> Tuple[int, int]:
    """
    Map all rows in a batch using the selected MappingProfile.
    Persists:
      - parsed (JSON-safe dict)
      - norm_date (date), norm_amount (Decimal), norm_description (str)
      - suggestions (e.g., {'subcategory': '...'})
      - errors (list[str])
      - is_duplicate (bool)
    Returns: (updated_count, duplicate_count)
    """
    assert batch is not None, "batch is required"

    mapping = getattr(profile, "column_map", None)
    if not isinstance(mapping, dict):
        raise TypeError(f"MappingProfile.column_map must be dict; got {type(mapping)}")

    updated = 0
    dup_count = 0

    rows = batch.rows.order_by("row_index").all()
    for row in rows:
        try:
            # Your existing routine that applies the profile and returns a dict:
            # expects keys like: date/description/amount + _date/_amount/_suggestions/_errors
            out = map_row_with_profile(row.raw, profile)

            # JSON blob must be serializable
            json_safe_out = {k: _json_safe(v) for k, v in out.items()}

            # Denormalized fields (native types for querying)
            norm_date = out.get("_date") or None
            amt = out.get("_amount")
            if isinstance(amt, Decimal):
                norm_amount = amt
            elif amt in (None, ""):
                norm_amount = None
            else:
                # be forgiving if a float/int sneaks through
                try:
                    norm_amount = Decimal(str(amt))
                except (InvalidOperation, TypeError, ValueError):
                    norm_amount = None

            norm_description = (out.get("description") or "").strip()

            # Suggestions (augment with categorization if not present)
            suggestions = out.get("_suggestions") or {}
            if "subcategory" not in suggestions:
                sug = suggest_subcategory(norm_description) or ""
                if sug:
                    suggestions["subcategory"] = sug

            errors = out.get("_errors") or []

            # Duplicate check payload (prefer normalized values)
            dup_payload = {
                "date": norm_date,
                "amount": norm_amount,
                "description": norm_description,
                # bank account is chosen at commit time; only use hint now
                "bank_account": bank_account_hint or "",
            }
            is_dup = bool(is_duplicate(dup_payload))

            if is_dup:
                dup_count += 1

            # Persist to row
            row.parsed = json_safe_out
            row.norm_date = norm_date
            row.norm_amount = norm_amount
            row.norm_description = norm_description
            row.suggestions = suggestions
            row.errors = errors
            row.is_duplicate = is_dup
            # avoid referencing non-existent columns in update_fields
            row.save(update_fields=[
                "parsed",
                "norm_date",
                "norm_amount",
                "norm_description",
                "suggestions",
                "errors",
                "is_duplicate",
                "updated_at" if hasattr(row, "updated_at") else "norm_description"  # harmless re-save if no updated_at
            ])

            updated += 1

        except Exception:
            # Record mapping error, keep going
            errs = list(row.errors or [])
            errs.append("map: unexpected failure (see logs)")
            row.errors = errs
            try:
                row.save(update_fields=["errors"])
            except Exception:
                # last‑ditch — don’t let a bad row block the rest
                logger.warning(
                    "Failed to save errors for row %s in batch %s",
                    row.row_index, batch.pk, exc_info=True
                )
            logger.warning(
                "Mapping error on row %s in batch %s (raw=%r)",
                row.row_index, batch.pk, row.raw, exc_info=True
            )
            continue

    # Always assign the profile and set status to previewed, then save
    batch.profile = profile
    batch.status = "previewed"
    batch.save()

    return updated, dup_count

@trace
def commit_batch(batch: ImportBatch, bank_account: str) -> Tuple[List[int], List[int], List[int]]:
    """
    Persist non-duplicate rows as Transactions.
    Uses per-row savepoints so a single bad row doesn't poison the whole transaction.
    Returns (imported_row_indices, duplicate_row_indices, skipped_row_indices)
    """
    imported, duplicates, skipped = [], [], []

    # Cache allowed concrete fields to avoid passing stray keys to the model
    allowed_fields = {
        f.name for f in Transaction._meta.get_fields()
        if getattr(f, "concrete", False) and not f.auto_created and not f.many_to_many
    }

    with dbtx.atomic():
        # optional: set batch status
        if hasattr(batch, "status"):
            batch.status = "committing"
            batch.save(update_fields=["status"])

        qs = batch.rows.all()
        for row in qs:
            if row.is_duplicate:
                duplicates.append(row.row_index)
                continue

            # Build transaction payload from normalized + parsed
            parsed = row.parsed or {}
            data = {
                "date": row.norm_date,
                "amount": row.norm_amount,
                "description": row.norm_description or (parsed.get("description") or ""),
                "bank_account": bank_account,
                "source": getattr(batch, "filename", "") or f"batch:{batch.pk}",
            }

            # Resolve FK suggestions (best-effort)
            sugg = row.suggestions or parsed.get("_suggestions") or {}
            sub_name = sugg.get("subcategory")
            if sub_name:
                sub = Category.objects.filter(name=sub_name).first()
                if sub:
                    data["subcategory"] = sub

            pyo_name = sugg.get("payoree")
            if pyo_name:
                pyo = Payoree.get_existing(pyo_name) or Payoree.objects.create(name=pyo_name)
                data["payoree"] = pyo

            # Strip non-model keys
            sanitized = {k: v for k, v in data.items() if k in allowed_fields}

            if not data["date"] or data["amount"] is None:
                errs = list(row.errors or [])
                errs.append("commit: missing required date/amount")
                row.errors = errs
                row.save(update_fields=["errors"])
                skipped.append(row.row_index)
                continue

            try:
                with dbtx.atomic():  # savepoint per row
                    obj = Transaction.objects.create(**sanitized)
                    row.committed_txn_id = obj.pk
                    row.save(update_fields=["committed_txn_id"])
                    imported.append(row.row_index)
            except Exception:
                # capture and persist row-level error; do not break the loop
                errs = list(row.errors or [])
                errs.append("commit: failed to create Transaction (see logs)")
                row.errors = errs
                row.save(update_fields=["errors"])
                skipped.append(row.row_index)
                logger.warning(
                    "Commit failed for row %s in batch %s (payload=%s)",
                    row.row_index, batch.pk, sanitized, exc_info=True
                )

        # finalize status
        if hasattr(batch, "status"):
            batch.status = "committed"
            batch.save(update_fields=["status"])

    return imported, duplicates, skipped