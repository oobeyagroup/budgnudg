# transactions/services/import_flow.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable, Tuple
from decimal import Decimal
import datetime as dt
from django.db import transaction as dj_txn, IntegrityError
from transactions.models import Transaction, Category, Payoree
from transactions.services import mapping as map_svc  # your existing mapping helpers
from transactions.services.helpers import (
    json_safe_rows, coerce_row_for_model, is_duplicate
)

SESSION = {
    "upload_blob": "import_upload_blob",
    "upload_name": "import_upload_name",
    "profile": "import_profile",
    "bank": "import_bank",
    "parsed": "parsed_transactions",
    "index": "review_index",
}

def seed_session(session: dict, *, text: str, filename: str, profile: str, bank: str) -> None:
    session[SESSION["upload_blob"]] = text
    session[SESSION["upload_name"]] = filename
    session[SESSION["profile"]] = profile
    session[SESSION["bank"]] = bank
    session[SESSION["index"]] = 0

def parse_preview(session: dict) -> list[dict[str, Any]]:
    text = session[SESSION["upload_blob"]]
    profile = session[SESSION["profile"]]
    bank = session[SESSION["bank"]]
    rows = map_svc.map_csv_text_to_transactions(text, profile, bank)
    session[SESSION["parsed"]] = json_safe_rows(rows)
    session[SESSION["index"]] = 0
    return session[SESSION["parsed"]]

def get_current_row(session: dict) -> tuple[dict[str, Any] | None, int, int]:
    rows = session.get(SESSION["parsed"], [])
    idx = int(session.get(SESSION["index"], 0))
    if idx >= len(rows):
        return None, idx, len(rows)
    return rows[idx], idx, len(rows)

def apply_review(session: dict, cleaned: dict[str, Any]) -> None:
    rows = session.get(SESSION["parsed"], [])
    idx = int(session.get(SESSION["index"], 0))
    if idx < len(rows):
        rows[idx].update(cleaned)
        session[SESSION["parsed"]] = json_safe_rows(rows)
        session[SESSION["index"]] = idx + 1

def persist(rows: Iterable[dict[str, Any]]) -> tuple[list[Transaction], list[dict], list[dict]]:
    imported, duplicates, skipped = [], [], []

    allowed = {
        f.name for f in Transaction._meta.get_fields()
        if getattr(f, "concrete", False) and not f.auto_created and not f.many_to_many
    }

    for raw in rows:
        if raw.get("_is_duplicate"):
            duplicates.append(raw); continue

        try:
            data = coerce_row_for_model(raw)
        except Exception as e:
            raw["_error"] = str(e)
            skipped.append(raw); continue

        # Resolve FK strings if present
        if isinstance(data.get("subcategory"), str):
            data["subcategory"] = Category.objects.filter(name=data["subcategory"]).first()
        if isinstance(data.get("payoree"), str):
            p = Payoree.get_existing(data["payoree"]) or (Payoree.objects.create(name=data["payoree"]) if data["payoree"] else None)
            data["payoree"] = p

        if is_duplicate(data):
            duplicates.append(raw); continue

        sanitized = {k: v for k, v in data.items() if k in allowed}
        try:
            with dj_txn.atomic():
                obj = Transaction.objects.create(**sanitized)
            imported.append(obj)
        except IntegrityError as e:
            raw["_error"] = f"DB error: {e}"
            skipped.append(raw)

    return imported, duplicates, skipped