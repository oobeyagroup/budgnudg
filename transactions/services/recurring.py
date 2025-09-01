from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone

from transactions.models import Transaction, RecurringSeries


def cents(amount: Decimal | float | int) -> int:
    """Return absolute cents as int, using half-up rounding for Decimal."""
    if amount is None:
        return 0
    if isinstance(amount, Decimal):
        q = (abs(amount) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        return int(q)
    return int(round(abs(float(amount)) * 100))


def payoree_key_for(txn: Transaction) -> str:
    if getattr(txn, "payoree_id", None) and getattr(txn, "payoree", None):
        try:
            return txn.payoree.name.strip().lower()
        except Exception:
            pass
    return txn.description.strip().lower() or "unknown"


def seed_series_from_transaction(txn: Transaction) -> RecurringSeries:
    bucket = cents(txn.amount)

    existing = RecurringSeries.objects.filter(payoree=txn.payoree, amount_cents=bucket).first()
    if existing:
        if not existing.active:
            existing.active = True
        if txn.date and (existing.last_seen is None or txn.date > existing.last_seen):
            existing.last_seen = txn.date
        # update seed_transaction if missing
        if not existing.seed_transaction:
            existing.seed_transaction = txn
        existing.save(update_fields=["active", "last_seen", "seed_transaction"])
        return existing

    return RecurringSeries.objects.create(
        payoree=txn.payoree,
        amount_cents=bucket,
        interval="monthly",
        confidence=0.60,
        first_seen=txn.date or timezone.now().date(),
        last_seen=txn.date or timezone.now().date(),
        next_due=None,
        active=True,
        notes="Seeded from Similar Transactions action.",
        seed_transaction=txn,
    )
