# ingest/services/matching.py
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from transactions.models import Transaction

AMOUNT_TOL = Decimal("0.01")  # exact is best; tiny tolerance ok

@dataclass
class Candidate:
    txn: Transaction
    score: int
    why: list[str]

def _score_candidate(
    txn: Transaction, *, bank: str, check_no: str, amount: Decimal | None
) -> Candidate:
    score = 0
    why: list[str] = []
    if txn.bank_account == bank:
        score += 3; why.append("✓ bank")
    if check_no and f"CHECK {check_no}" in (txn.description or "").upper():
        score += 3; why.append(f"✓ 'CHECK {check_no}'")
    if amount is not None and txn.amount is not None:
        if abs(txn.amount - amount) <= AMOUNT_TOL:
            score += 3; why.append("✓ amount")
    return Candidate(txn=txn, score=score, why=why)

def find_candidates(
    *, bank: str, check_no: str, amount: Decimal | None, limit: int = 10
) -> list[Candidate]:
    qs = Transaction.objects.all()
    if bank:
        qs = qs.filter(bank_account=bank)
    if check_no:
        qs = qs.filter(description__icontains=f"CHECK {check_no}")
    if amount is not None:
        # don’t over-filter; we’ll score on amount exactly
        pass

    ranked = [
        _score_candidate(t, bank=bank, check_no=check_no, amount=amount)
        for t in qs.select_related("subcategory")
    ]
    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked[:limit]

def render_description(csv_desc: str, *, check_no: str|None, payoree: str|None, memo: str|None) -> str:
    parts: list[str] = []
    if csv_desc: parts.append(csv_desc)
    if check_no: parts.append(f"Check #{check_no}")
    if payoree:  parts.append(f"Payee: {payoree}")
    if memo:     parts.append(f"Memo: {memo}")
    return " | ".join(parts)
