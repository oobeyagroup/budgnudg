# transactions/views/mixins.py
from __future__ import annotations
from typing import Any, Iterable
from django.shortcuts import redirect
from django.contrib import messages
from django.db import IntegrityError, transaction
from transactions.models import Transaction, Category, Payoree
from transactions.services.helpers import coerce_row_for_model, is_duplicate
from django.utils.decorators import method_decorator
from transactions.utils import trace


SESSION_KEYS = {
    "upload_blob": "import_file",           # file contents as text (utf-8-sig)
    "upload_name": "import_file_name",
    "profile": "import_profile",
    "bank": "import_bank_account",
    "parsed": "parsed_transactions",        # list[dict] for preview/review
    "index": "review_index",                # current row pointer for review
}

class ImportSessionMixin:
    """Centralizes all session key access & mutations for import views."""
    @method_decorator(trace)
    # ---- choices helpers (override if you want)
    def profile_choices(self) -> list[tuple[str, str]]:
        # Replace with DB-backed profiles when you move off the JSON file
        from transactions.utils import load_mapping_profiles
        profiles = load_mapping_profiles().keys()
        return [(p, p) for p in profiles]

    def account_choices(self) -> list[tuple[str, str]]:
        from transactions.models import Transaction
        accounts = (
            Transaction.objects.exclude(bank_account__isnull=True)
            .exclude(bank_account__exact="")
            .values_list("bank_account", flat=True)
            .distinct()
        )
        return [(a, a) for a in accounts]

    # ---- upload state
    def save_upload_to_session(self, request, form) -> None:
        file = form.cleaned_data["file"]
        profile = form.cleaned_data["mapping_profile"]
        bank = form.cleaned_data["bank_account"]

        # Read file contents as text (utf-8-sig)
        from transactions.services.helpers import read_uploaded_text
        text, name = read_uploaded_text(file)

        s = request.session
        s[SESSION_KEYS["upload_blob"]] = text
        s[SESSION_KEYS["upload_name"]] = name
        s[SESSION_KEYS["profile"]] = profile
        s[SESSION_KEYS["bank"]] = bank
        s[SESSION_KEYS["index"]] = 0  # reset review pointer

    def read_session_upload(self, request) -> tuple[str, str, str]:
        s = request.session
        try:
            return (
                s[SESSION_KEYS["upload_blob"]],
                s[SESSION_KEYS["profile"]],
                s[SESSION_KEYS["bank"]],
            )
        except KeyError:
            messages.error(request, "Import session missing. Please upload again.")
            raise

    # ---- parsed rows
    def save_parsed(self, request, rows: list[dict[str, Any]]) -> None:
        """Persist preview/review rows into session (ensure JSON-safe types)."""
        from transactions.services.helpers import json_safe_rows
        request.session[SESSION_KEYS["parsed"]] = json_safe_rows(rows)
        request.session[SESSION_KEYS["index"]] = 0

    def get_parsed(self, request) -> list[dict[str, Any]]:
        return request.session.get(SESSION_KEYS["parsed"], [])

    # ---- review flow helpers
    def current_row(self, request) -> tuple[dict[str, Any] | None, int, int]:
        rows = self.get_parsed(request)
        idx = int(request.session.get(SESSION_KEYS["index"], 0))
        if idx >= len(rows):
            return None, idx, len(rows)
        return rows[idx], idx, len(rows)

    def apply_review(self, request, cleaned: dict[str, Any]) -> None:
        rows = self.get_parsed(request)
        idx = int(request.session.get(SESSION_KEYS["index"], 0))
        if idx >= len(rows):
            return
        # merge back
        rows[idx].update(cleaned)
        # ensure JSON-safe after user edits
        from transactions.services.helpers import json_safe_rows
        request.session[SESSION_KEYS["parsed"]] = json_safe_rows(rows)
        request.session[SESSION_KEYS["index"]] = idx + 1

    # ---- finalize save
    def persist_rows(self, rows):
        imported, duplicates, skipped = [], [], []

        # Build the allowed field set from the model (no duplication, future‑proof)
        allowed = {
            f.name
            for f in Transaction._meta.get_fields()
            if getattr(f, "concrete", False) and not f.auto_created and not f.many_to_many
        }

        for raw in rows:
            # honor pre-flagged dups
            if raw.get("_is_duplicate"):
                duplicates.append(raw)
                continue

            try:
                data = coerce_row_for_model(raw)  # parse date/amount; clean empties
            except Exception as e:
                raw["_error"] = str(e)
                skipped.append(raw)
                continue

            # resolve FK names to objects (if provided as strings)
            if isinstance(data.get("subcategory"), str):
                sub = Category.objects.filter(name=data["subcategory"]).first()
                data["subcategory"] = sub
            if isinstance(data.get("payoree"), str):
                pyo = Payoree.get_existing(data["payoree"]) or Payoree.objects.create(name=data["payoree"])
                data["payoree"] = pyo

            # runtime duplicate check
            if is_duplicate(data):
                duplicates.append(raw)
                continue

            # 🔒 strip any non-model keys (e.g., _is_duplicate, suggestions, etc.)
            sanitized = {k: v for k, v in data.items() if k in allowed}

            try:
                with transaction.atomic():
                    obj = Transaction.objects.create(**sanitized)
                imported.append(obj)
            except IntegrityError as e:
                raw["_error"] = f"DB integrity error: {e}"
                skipped.append(raw)

        return imported, duplicates, skipped