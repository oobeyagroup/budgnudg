import datetime as dt
from decimal import Decimal, InvalidOperation
from ingest.models import MappingProfile, ImportBatch, ImportRow
from django.db import transaction as dbtx
import logging
from typing import Tuple, List
# from .utils import parse_date

from transactions.categorization import suggest_subcategory, suggest_payoree  # your existing function
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
            logger.debug(f"Processing amount: csv_col='{csv_col}', raw_value='{raw}', type={type(raw)}")
            try: 
                out["_amount"] = Decimal(raw.replace(",",""))
                logger.debug(f"Parsed amount successfully: {out['_amount']}")
            except (InvalidOperation, AttributeError) as e: 
                logger.debug(f"Amount parsing failed: {e}")
                errors.append(f"amount: {e}")
        else:
            out[model_field] = raw
            
    # Enhanced categorization using multiple fields
    desc = out.get("description", "")
    memo = out.get("memo", "")
    payoree_field = out.get("payoree", "")
    
    # Combine available text fields for better analysis
    combined_text = " ".join(filter(None, [desc, memo, payoree_field]))
    
    # Get suggestions using the combined text
    suggested_subcategory = suggest_subcategory(combined_text) or ""
    suggested_payoree = suggest_payoree(combined_text) or ""
    
    # Build suggestions dict
    suggestions = {}
    if suggested_subcategory:
        suggestions["subcategory"] = suggested_subcategory
    if suggested_payoree:
        suggestions["payoree"] = suggested_payoree
        
    out["_suggestions"] = suggestions
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

            # Suggestions (use enhanced multi-field suggestions from mapping phase)
            suggestions = out.get("_suggestions") or {}
            
            # If no suggestions were generated during mapping, fall back to description-only analysis
            if not suggestions.get("subcategory"):
                logger.debug("DEBUG: No multi-field subcategory found, falling back to description analysis")
                # Enhanced analysis combining available fields
                desc = norm_description
                memo = out.get("memo", "")
                payoree_field = out.get("payoree", "")
                combined_text = " ".join(filter(None, [desc, memo, payoree_field]))
                logger.debug("DEBUG: Combined text for analysis: '%s'", combined_text[:100])
                
                sug = suggest_subcategory(combined_text) or ""
                if sug:
                    suggestions["subcategory"] = sug
                    logger.debug("DEBUG: Generated subcategory suggestion: '%s'", sug)
            
            # Also suggest payoree if not present
            if not suggestions.get("payoree"):
                logger.debug("DEBUG: No multi-field payoree found, falling back to description analysis")
                desc = norm_description
                memo = out.get("memo", "")
                payoree_field = out.get("payoree", "")
                combined_text = " ".join(filter(None, [desc, memo, payoree_field]))
                
                payoree_sug = suggest_payoree(combined_text) or ""
                if payoree_sug:
                    suggestions["payoree"] = payoree_sug
                    logger.debug("DEBUG: Generated payoree suggestion: '%s'", payoree_sug)

            # Debug logging for suggestions
            logger.debug("DEBUG: Row %s - Description: '%s'", row.row_index, norm_description[:50])
            logger.debug("DEBUG: Row %s - Subcategory suggestion: '%s'", row.row_index, suggestions.get("subcategory", "NONE"))
            logger.debug("DEBUG: Row %s - Payoree suggestion: '%s'", row.row_index, suggestions.get("payoree", "NONE"))

            errors = out.get("_errors") or []

            # Duplicate check payload (prefer normalized values)
            dup_payload = {
                "date": norm_date,
                "amount": norm_amount,
                "description": norm_description,
                "bank_account": bank_account_hint or "",  # Empty bank_account will check all accounts
            }
            is_dup = bool(is_duplicate(dup_payload))
            
            # Debug logging to track duplicate detection
            logger.debug("Duplicate check for row %s: date=%s, amount=%s, desc='%s', bank='%s' -> is_dup=%s", 
                        row.row_index, norm_date, norm_amount, norm_description[:50], 
                        bank_account_hint or "EMPTY", is_dup)

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
            
            # Debug logging for commit resolution
            logger.debug("DEBUG COMMIT: Row %s suggestions dict: %s", getattr(row, 'row_index', 'unknown'), sugg)
            
            # Priority 1: CSV Category field (from parsed data) - this takes precedence
            csv_category_name = parsed.get("subcategory")  # Note: CSV 'Category' maps to 'subcategory' field in profile
            logger.debug("DEBUG COMMIT: CSV category from parsed data: '%s'", csv_category_name)
            
            # Priority 2: AI-suggested subcategory (from suggestions) - fallback if no CSV category
            ai_sub_name = sugg.get("subcategory")
            logger.debug("DEBUG COMMIT: AI suggested subcategory name: '%s'", ai_sub_name)
            
            # Use CSV category if available, otherwise fall back to AI suggestion
            final_subcategory_name = csv_category_name or ai_sub_name
            logger.debug("DEBUG COMMIT: Final subcategory name (CSV takes precedence): '%s'", final_subcategory_name)
            
            if final_subcategory_name:
                subcategory_obj = Category.objects.filter(name=final_subcategory_name).first()
                logger.debug("DEBUG COMMIT: Found subcategory object: %s", subcategory_obj)
                if subcategory_obj:
                    data["subcategory"] = subcategory_obj
                    logger.debug("DEBUG COMMIT: Added subcategory to data: %s", subcategory_obj)

            pyo_name = sugg.get("payoree")
            logger.debug("DEBUG COMMIT: Extracted payoree name: '%s'", pyo_name)
            if pyo_name:
                pyo = Payoree.get_existing(pyo_name) or Payoree.objects.create(name=pyo_name)
                data["payoree"] = pyo

            # Strip non-model keys
            sanitized = {k: v for k, v in data.items() if k in allowed_fields}
            
            # Debug final data being sent to create
            logger.debug("DEBUG COMMIT: Full data dict: %s", data)
            logger.debug("DEBUG COMMIT: Sanitized data for create: %s", sanitized)
            logger.debug("DEBUG COMMIT: Has subcategory in sanitized: %s", 'subcategory' in sanitized)
            logger.debug("DEBUG COMMIT: Subcategory value: %s", sanitized.get('subcategory'))

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