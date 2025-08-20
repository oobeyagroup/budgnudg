from django.views.generic import ListView
from django.db.models import Q
from transactions.models import Transaction
from django.utils.decorators import method_decorator
from transactions.utils import trace
import logging

logger = logging.getLogger(__name__)

class TransactionListView(ListView):
    template_name = "transactions/transactions_list.html"
    context_object_name = "transactions"
    # Remove paginate_by to let DataTables handle pagination
    # paginate_by = 50
    ordering = "-date"  # default

    @method_decorator(trace)
    def get_queryset(self):
        qs = Transaction.objects.select_related("category", "subcategory", "payoree").all()

        # --- filters via query params ---
        account = self.request.GET.get("account")
        if account:
            qs = qs.filter(bank_account=account)

        if self.request.GET.get("uncategorized") == "1":
            # With new model: transactions missing payoree are "uncategorized" 
            # (since all transactions have a category now)
            qs = qs.filter(Q(payoree__isnull=True) | Q(payoree__name=""))

        if self.request.GET.get("no_category") == "1":
            qs = qs.filter(Q(category__isnull=True))

        if self.request.GET.get("no_payoree") == "1":
            qs = qs.filter(Q(payoree__isnull=True) | Q(payoree__name=""))

        # search in description
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(description__icontains=q.strip())

        # ordering override (?order=date or -amount etc.)
        order = self.request.GET.get("order")
        if order:
            qs = qs.order_by(order)

        return qs

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        from django.conf import settings
        ctx = super().get_context_data(**kwargs)
        # Surface current filters so the template can keep UI state
        ctx["current_filters"] = {
            "account": self.request.GET.get("account", ""),
            "uncategorized": self.request.GET.get("uncategorized", ""),
            "no_category": self.request.GET.get("no_category", ""),
            "no_payoree": self.request.GET.get("no_payoree", ""),
            "q": self.request.GET.get("q", ""),
            "order": self.request.GET.get("order", "-date"),
        }
        # Explicitly add debug setting to context
        ctx["debug"] = settings.DEBUG
        return ctx