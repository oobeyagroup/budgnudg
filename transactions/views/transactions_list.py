from django.views.generic import ListView
from django.db.models import Q
from transactions.models import Transaction
from transactions.filtering import get_filtered_transaction_queryset
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
        return get_filtered_transaction_queryset(self.request)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        from django.conf import settings
        from ingest.models import FinancialAccount
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
        # Add available bank accounts for filtering
        ctx["available_accounts"] = FinancialAccount.objects.all().order_by("name")
        # Explicitly add debug setting to context
        ctx["debug"] = settings.DEBUG
        return ctx