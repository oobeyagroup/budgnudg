# transactions/services/helpers.py
from __future__ import annotations
import csv
from io import StringIO, TextIOBase
import logging
from typing import Iterable, Iterator, Any, Dict
from decimal import Decimal, InvalidOperation
import datetime as dt
from transactions.utils import trace

logger = logging.getLogger(__name__)

@trace
def read_uploaded_text(django_file) -> tuple[str, str]:
    """
    Read an uploaded file-like object from a Django form into a decode-safe text string.
    Returns (text, original_filename).
    """
    name = getattr(django_file, "name", "uploaded.csv")
    # decode with utf-8-sig to handle BOM; fall back to plain utf-8
    try:
        text = django_file.read().decode("utf-8-sig")
    except AttributeError:
        # already str-like?
        text = django_file.read()
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    return text, name

@trace
def iter_csv(file_or_text) -> Iterable[Dict[str, Any]]:
    """
    Yield dict rows from CSV:
      - Accepts str, bytes, or file-like.
      - Decodes UTF-8 with BOM.
      - Skips blank lines/fully-empty rows.
      - Strips header/value whitespace.
    """
    # Normalize to text
    if hasattr(file_or_text, "read"):
        content = file_or_text.read()
    else:
        content = file_or_text

    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    elif isinstance(content, str):
        text = content
    else:
        text = str(content)

    # Let csv handle newlines; skipinitialspace trims after delimiters
    sio = StringIO(text)
    reader = csv.DictReader(sio, skipinitialspace=True)

    for i, row in enumerate(reader, start=1):
        # Strip header keys and values
        cleaned = {}
        for k, v in row.items():
            key = (k.strip() if isinstance(k, str) else k)
            val = (v.strip() if isinstance(v, str) else v)
            cleaned[key] = val
        # Skip fully empty rows
        if not any((str(v).strip() if v is not None else "") for v in cleaned.values()):
            logger.warning("iter_csv: skipping empty row at data index %d", i)
            continue
        yield cleaned

@trace
def parse_date(value: str | dt.date | None) -> dt.date | None:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    value = value.strip()
    # common formats
    fmts = ("%Y-%m-%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y")
    for fmt in fmts:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    # last resort: ISO-ish like 2025/07/11
    try:
        return dt.date.fromisoformat(value.replace("/", "-"))
    except Exception:
        return None

@trace
def to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    # strip currency symbols/commas
    s = str(value).replace(",", "").replace("$", "").strip()
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None

@trace
def json_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert non-JSON types (date, Decimal) to strings for session storage.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        copy = {}
        for k, v in r.items():
            if isinstance(v, dt.date):
                copy[k] = v.isoformat()
            elif isinstance(v, Decimal):
                copy[k] = str(v)
            else:
                copy[k] = v
        out.append(copy)
    return out

@trace
def coerce_row_for_model(row: dict[str, Any]) -> dict[str, Any]:
    """
    Prepare a row (possibly stringly-typed from session) for Transaction(**data).
    """
    data = dict(row)
    # date
    if isinstance(data.get("date"), str):
        data["date"] = parse_date(data["date"])
    # amount
    if isinstance(data.get("amount"), str):
        data["amount"] = to_decimal(data["amount"])
    # clean empties to None (let model defaults/NULLs apply)
    for k, v in list(data.items()):
        if isinstance(v, str) and v.strip() == "":
            data[k] = None
    return data

@trace
def is_duplicate(data: dict[str, Any]) -> bool:
    from transactions.models import Transaction
    return Transaction.objects.filter(
        date=data.get("date"),
        amount=data.get("amount"),
        description=data.get("description"),
        bank_account=data.get("bank_account"),
    ).exists()