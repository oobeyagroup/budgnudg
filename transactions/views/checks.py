# transactions/views/checks.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction as dbtx
from decimal import Decimal
from transactions.selectors import check_like_transactions, extract_check_number_from_description
from ingest.models import ScannedCheck  # adjust import path
from transactions.models import Transaction
from transactions.utils import trace

@trace
def check_reconcile(request):
    account = request.GET.get("account") or ""
    txns = check_like_transactions(account=account)
    checks = ScannedCheck.objects.filter(matched_transaction__isnull=True)
    context = {
        "account": account,
        "transactions": txns,
        "checks": checks.order_by("-date", "-id"),
    }
    return render(request, "transactions/checks_reconcile.html", context)

@trace
@require_POST
def match_check(request):
    check_id = request.POST.get("check_id")
    txn_id = request.POST.get("txn_id")
    payee = request.POST.get("payee") or ""
    memo = request.POST.get("memo") or ""

    check = get_object_or_404(ScannedCheck, pk=check_id)
    txn = get_object_or_404(Transaction, pk=txn_id)

    with dbtx.atomic():
        # link
        check.matched_transaction = txn
        check.save(update_fields=["matched_transaction"])

        # optionally set payee/memo on the txn if missing
        updates = []
        if payee and not getattr(txn, "payoree", None):
            # if you have a Payoree model with a helper:
            from transactions.models import Payoree
            pyo = Payoree.get_existing(payee) or Payoree.objects.create(name=payee)
            txn.payoree = pyo
            updates.append("payoree")
        if memo and not txn.memo:
            txn.memo = memo
            updates.append("memo")
        if updates:
            txn.save(update_fields=updates)

    messages.success(request, f"Matched check {check.check_number} to txn {txn.pk}.")
    return redirect("transactions:checks_reconcile")

@trace
@require_POST
def unlink_check(request, check_id: int):
    check = get_object_or_404(ScannedCheck, pk=check_id)
    check.matched_transaction = None
    check.save(update_fields=["matched_transaction"])
    messages.info(request, f"Unlinked check {check.check_number}.")
    return redirect("transactions:checks_reconcile")