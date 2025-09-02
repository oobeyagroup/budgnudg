import os
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseNotAllowed
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from transactions.services.recurring import seed_series_from_transaction

from transactions.models import Transaction, Payoree


def _test_api_allowed():
    # Only allow when DEBUG or explicit env var set
    return getattr(settings, "DEBUG", False) or os.environ.get("ENABLE_TEST_API") == "1"


@csrf_exempt
@require_POST
def create_test_transaction(request):
    if not _test_api_allowed():
        return HttpResponseForbidden("Test API disabled")

    # Expect JSON payload or form data with minimal fields
    data = request.POST or request.body
    # Simple extraction, prefer POST form
    desc = (
        request.POST.get("description")
        or request.GET.get("description")
        or "Test Merchant"
    )
    amount = request.POST.get("amount") or request.GET.get("amount") or "-1.00"
    pay_name = (
        request.POST.get("payoree") or request.GET.get("payoree") or "Test Payoree"
    )

    pay, _ = Payoree.objects.get_or_create(name=pay_name)

    txn = Transaction.objects.create(
        source="test-api",
        bank_account=None,
        sheet_account="checking",
        date=request.POST.get("date") or request.GET.get("date") or timezone.now(),
        description=desc,
        amount=Decimal(amount),
        account_type="checking",
        payoree=pay,
    )

    return JsonResponse({"id": txn.id, "description": txn.description})


@require_GET
def check_series_for_seed(request, txn_id: int):
    if not _test_api_allowed():
        return HttpResponseForbidden("Test API disabled")

    from transactions.models import RecurringSeries

    # First check direct seed_transaction link
    exists = RecurringSeries.objects.filter(seed_transaction_id=txn_id).exists()
    if exists:
        return JsonResponse({"exists": True})

    # Otherwise, consider a matching series by payoree and amount_cents as equivalent
    try:
        txn = Transaction.objects.get(id=txn_id)
    except Transaction.DoesNotExist:
        return JsonResponse({"exists": False})

    # Use service helpers to compute payoree key and cents
    from transactions.services.recurring import payoree_key_for, cents

    pkey = payoree_key_for(txn)
    bucket = cents(txn.amount)
    exists = RecurringSeries.objects.filter(
        payoree=txn.payoree, amount_cents=bucket
    ).exists()
    return JsonResponse({"exists": exists})


@csrf_exempt
@require_POST
def seed_series_test_api(request, txn_id: int):
    """Test-only endpoint: create a RecurringSeries from an existing transaction id."""
    if not _test_api_allowed():
        return HttpResponseForbidden("Test API disabled")

    try:
        txn = Transaction.objects.get(id=txn_id)
    except Transaction.DoesNotExist:
        return JsonResponse({"error": "transaction not found"}, status=404)

    series = seed_series_from_transaction(txn)
    return JsonResponse({"series_id": series.id})


@require_GET
def debug_list_series_for_txn(request, txn_id: int):
    """Test-only debug endpoint: list recurring series rows and key fields for inspection."""
    if not _test_api_allowed():
        return HttpResponseForbidden("Test API disabled")

    from transactions.models import RecurringSeries

    qs = RecurringSeries.objects.filter(seed_transaction_id=txn_id)
    rows = [
        {
            "id": s.id,
            "seed_transaction_id": s.seed_transaction_id,
            "merchant_key": s.merchant_key,
            "amount_cents": s.amount_cents,
            "active": s.active,
        }
        for s in qs
    ]
    return JsonResponse({"series": rows})
