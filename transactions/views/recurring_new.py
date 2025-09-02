from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.utils.decorators import method_decorator

from transactions.models import Transaction
from transactions.services.recurring import seed_series_from_transaction
from transactions.utils import trace
from transactions.models import RecurringSeries
from django.views.decorators.http import require_POST
from django.utils import timezone


@method_decorator(trace, name="dispatch")
class UpdateSeedTxnView(View):
    """Find the most recent Transaction that matches a RecurringSeries
    (by payoree and amount_cents) and set it as the seed_transaction.
    """
    def post(self, request, series_id: int):
        series = get_object_or_404(RecurringSeries, pk=series_id)

        # Find most recent transaction with matching payoree and amount
        # Use the same helpers as the recurring service so we normalize payoree
        # keys the same way and compare cents.
        from transactions.services.recurring import payoree_key_for, cents

        qs = Transaction.objects.select_related("payoree").all().order_by("-date", "-id")

        latest = None
        for txn in qs:
            try:
                if payoree_key_for(txn) == payoree_key_for(series.seed_transaction or txn) and cents(txn.amount) == (series.amount_cents or 0):
                    latest = txn
                    break
            except Exception:
                continue
        if latest:
            series.seed_transaction = latest
            series.last_seen = latest.date
            series.save(update_fields=["seed_transaction", "last_seen"])
            from django.contrib import messages
            messages.success(request, f"Seed transaction updated to T{latest.id}.")
        else:
            from django.contrib import messages
            messages.warning(request, "No matching transaction found to update seed.")

        return redirect(request.META.get("HTTP_REFERER") or "/transactions/recurring/")


@method_decorator(trace, name="dispatch")
class CreateRecurringFromTransactionView(View):
    def post(self, request, pk: int):
        txn = get_object_or_404(Transaction, pk=pk)
        series = seed_series_from_transaction(txn)
        payoree_name = series.payoree.name if series.payoree else "Unknown"
        messages.success(
            request,
            f"Recurring series created for "{payoree_name}" at ~${series.amount_cents/100:.2f}."
        )
        return redirect(request.META.get("HTTP_REFERER") or "/")
