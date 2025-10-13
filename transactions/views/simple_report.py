"""
Simple Transaction Report View
Shows a clean glassmorphism table with 10 recent transactions
"""

from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from transactions.models import Transaction
from transactions.utils import trace


class SimpleTransactionReportView(TemplateView):
    template_name = "transactions/simple_report.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get 10 most recent transactions with related data
        transactions = Transaction.objects.select_related(
            "category", "subcategory"
        ).order_by("-date", "-id")[:10]

        context.update(
            {
                "transactions": transactions,
                "total_count": transactions.count(),
            }
        )

        return context
