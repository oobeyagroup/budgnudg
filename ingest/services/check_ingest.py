import hashlib
from datetime import timedelta
from decimal import Decimal
from django.db import transaction as dbtx
from django.db.models import Q
from transactions.models import Transaction, Category, Payoree
from ingest.models import ScannedCheck

def md5_bytes(b: bytes) -> str:
    h = hashlib.md5()
    h.update(b)
    return h.hexdigest()

def save_uploaded_checks(files) -> tuple[list[ScannedCheck], list[str]]:
    """
    Save uploaded images into ScannedCheck rows, deduping by content_md5.
    Returns (created_checks, skipped_filenames).
    """
    created, skipped = [], []
    for f in files:
        content = f.read()
        f.seek(0)
        digest = md5_bytes(content)
        if ScannedCheck.objects.filter(content_md5=digest).exists():
            skipped.append(getattr(f, "name", "unknown"))
            continue
        sc = ScannedCheck.objects.create(
            image_file=f, original_filename=getattr(f, "name", ""), content_md5=digest
        )
        created.append(sc)
    return created, skipped

def candidate_transactions(bank_account: str, date, amount: Decimal, check_number: str | None):
    """
    Find likely matches. Strategy:
      - same bank_account
      - date within ±5 days
      - amount equal (abs)
      - optional: description contains 'CHECK ####'
    """
    qs = Transaction.objects.filter(
        bank_account=bank_account,
        date__gte=date - timedelta(days=5),
        date__lte=date + timedelta(days=5),
        amount=amount
    )
    if check_number:
        needle = f"CHECK {check_number}"
        qs = qs.filter(description__icontains=needle)
    return qs.order_by("date")[:25]

def suggest_subcategory_from_payoree(payoree: Payoree | None) -> Category | None:
    if not payoree:
        return None
    # Pull the most frequent existing subcategory used with this payoree.
    agg = (
        Transaction.objects
        .filter(payoree=payoree, subcategory__isnull=False)
        .values("subcategory")
        .annotate(n=models.Count("id"))
        .order_by("-n")
        .first()
    )
    if not agg:
        return None
    from transactions.models import Category
    return Category.objects.filter(pk=agg["subcategory"]).first()

@dbtx.atomic
def attach_or_create_transaction(sc: ScannedCheck, cleaned: dict) -> Transaction:
    """
    If cleaned['match_txn_id'] present, link to that transaction and update missing fields.
    Else create a Transaction from the cleaned fields.
    """
    bank_account = cleaned["bank_account"]
    check_number = cleaned.get("check_number") or ""
    date = cleaned["date"]
    amount = cleaned["amount"]
    payoree = cleaned.get("payoree")
    memo_text = cleaned.get("memo_text", "")

    if cleaned.get("match_txn_id"):
        txn = Transaction.objects.select_for_update().get(pk=cleaned["match_txn_id"])
        # Update txn with any missing/empty fields
        if not txn.payoree and payoree:
            txn.payoree = payoree
        if (not txn.description) and check_number:
            txn.description = f"CHECK {check_number}"
        if not txn.memo:
            txn.memo = memo_text
        txn.save()
    else:
        # New transaction (CSV secondary goal is respected: we’re only here if not matching)
        txn = Transaction.objects.create(
            date=date,
            amount=amount,
            description=f"CHECK {check_number}" if check_number else memo_text or "Check",
            bank_account=bank_account,
            payoree=payoree,
            memo=memo_text
        )

    # Optionally auto-suggest subcategory from payoree (don’t overwrite existing)
    if payoree and not txn.subcategory:
        sub = suggest_subcategory_from_payoree(payoree)
        if sub:
            txn.subcategory = sub
            txn.save(update_fields=["subcategory"])

    sc.transaction = txn
    sc.bank_account = bank_account
    sc.check_number = check_number
    sc.date = date
    sc.amount = amount
    sc.payoree = payoree
    sc.memo_text = memo_text
    sc.save()

    return txn
