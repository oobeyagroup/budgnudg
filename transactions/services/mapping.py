import csv, logging, re
from io import StringIO
from transactions.services.helpers import parse_date, to_decimal
from transactions.utils import trace
from transactions.utils import load_mapping_profiles as _load_mapping_profiles


logger = logging.getLogger(__name__)

@trace
def load_mapping_profiles():
    """Shim for tests and services; delegates to transactions.utils."""
    return _load_mapping_profiles()

@trace
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())

@trace
def map_file_for_profile(file_text: str, profile_name: str, bank_account: str) -> list[dict]:
    from transactions.utils import load_mapping_profiles
    profiles = load_mapping_profiles()
    mapping = profiles.get(profile_name, {}).get("mapping", {})
    if not mapping:
        logger.error("Mapping profile not found or empty: %s", profile_name)
        return []

    reader = csv.DictReader(StringIO(file_text))
    headers = reader.fieldnames or []
    logger.info("Import preview using profile %s; headers: %s",
                profile_name, ", ".join(headers))

    # Build normalization map from actual CSV headers
    norm_to_actual = {_norm(h): h for h in headers if h is not None}

    # Resolve the mapping keys to actual headers (exact or normalized)
    resolved: dict[str, str] = {}
    missing = []
    for csv_col, model_field in mapping.items():
        if csv_col in headers:
            resolved[csv_col] = model_field
        else:
            alt = norm_to_actual.get(_norm(csv_col))
            if alt:
                resolved[alt] = model_field
                logger.info("Header alias resolved: '%s' -> '%s'", csv_col, alt)
            else:
                missing.append(csv_col)

    if missing:
        logger.warning(
            "CSV missing mapped columns for profile %s: %s",
            profile_name, ", ".join(missing)
        )

    rows: list[dict] = []
    for csv_row in reader:
        model_row: dict = {}
        for actual_col, model_field in resolved.items():
            raw = (csv_row.get(actual_col) or "").strip()
            model_row[model_field] = raw

        # Coerce common fields
        if "date" in model_row:
            model_row["date"] = parse_date(model_row["date"])
        if "amount" in model_row:
            model_row["amount"] = to_decimal(model_row["amount"])

        model_row["bank_account"] = bank_account
        rows.append(model_row)

    return rows

@trace
def map_csv_text_to_transactions(text: str, profile_name: str, bank_account: str) -> list[dict]:
    """
    Stable entry point used by services/import_flow and tests.
    Accepts CSV *text*, applies the named mapping profile, injects bank_account,
    returns a list of transaction dicts suitable for preview/review/persist.
    """
    rows = list(iter_csv(StringIO(text)))
    return map_csv_rows_to_transactions(rows, profile_name, bank_account)


def map_csv_rows_to_transactions(rows: list[dict], profile_name: str, bank_account: str) -> list[dict]:
    """
    Core mapper from normalized CSV dict rows -> transaction dicts using a saved profile.
    """
    profiles = load_mapping_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        raise ValueError(f"Mapping profile '{profile_name}' not found.")

    mapping = profile.get("mapping", {})
    out: list[dict] = []

    for row in rows:
        txn = {
            "bank_account": bank_account,
            "_is_duplicate": False,  # caller may update this flag
        }

        for csv_col, model_field in mapping.items():
            raw = (row.get(csv_col) or "").strip()

            if model_field == "date":
                # leave as raw string; coerce later (coerce_row_for_model)
                txn["date"] = raw
            elif model_field == "amount":
                # keep raw -> coerce later; but if you want, you can pre-Decimal here
                txn["amount"] = raw
            elif model_field == "subcategory":
                txn["subcategory"] = raw  # will be resolved to FK later if present
            elif model_field == "payoree":
                txn["payoree"] = raw
            else:
                txn[model_field] = raw

        out.append(txn)

    return out

# transactions/services/mapping.py
def map_csv_file_to_transactions(text_or_file, profile_name: str = None, bank_account: str = None, **kwargs):
    # accept legacy aliases
    if profile_name is None:
        profile_name = kwargs.get("profile")
    if bank_account is None:
        bank_account = kwargs.get("bank") or kwargs.get("account")

    if hasattr(text_or_file, "read"):
        raw = text_or_file.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig", errors="replace")
        text = raw
    else:
        text = str(text_or_file)

    return map_csv_text_to_transactions(text, profile_name, bank_account)

# transactions/services/mapping.py
from io import StringIO
from typing import Any, List, Dict

from transactions.services.helpers import iter_csv
from transactions.utils import trace

# ensure you already have: def load_mapping_profiles(): ... returning {profile: {"mapping": {...}}}

def map_csv_rows_to_transactions(rows: List[Dict[str, Any]], profile_name: str, bank_account: str) -> List[Dict[str, Any]]:
    profiles = load_mapping_profiles()
    profile = profiles.get(profile_name)
    if not profile:
        raise ValueError(f"Mapping profile '{profile_name}' not found.")
    mapping = profile.get("mapping", {})

    out: List[Dict[str, Any]] = []
    for row in rows:
        txn = {"bank_account": bank_account, "_is_duplicate": False}
        for csv_col, model_field in mapping.items():
            raw = (row.get(csv_col) or "").strip()
            if model_field == "date":
                txn["date"] = raw                   # coerce later in coerce_row_for_model
            elif model_field == "amount":
                txn["amount"] = raw                 # coerce later
            else:
                txn[model_field] = raw              # includes subcategory, payoree, etc.
        out.append(txn)
    return out

@trace
def map_csv_text_to_transactions(text: str, profile_name: str, bank_account: str) -> List[Dict[str, Any]]:
    """Public entry point: CSV *text* -> preview rows."""
    rows = list(iter_csv(StringIO(text)))
    return map_csv_rows_to_transactions(rows, profile_name, bank_account)

# Back-compat: some call sites/tests may pass a file-like or text
def map_csv_file_to_transactions(text_or_file, profile_name: str, bank_account: str) -> List[Dict[str, Any]]:
    if hasattr(text_or_file, "read"):
        raw = text_or_file.read()
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8-sig", errors="replace")
        text = raw
    else:
        text = str(text_or_file)
    return map_csv_text_to_transactions(text, profile_name, bank_account)