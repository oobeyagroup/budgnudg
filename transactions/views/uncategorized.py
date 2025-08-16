# transactions/views/uncategorized.py
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from transactions.models import Transaction
from transactions.utils import trace

class UncategorizedTransactionsView(ListView):
    template_name = "transactions/uncategorized_list.html"
    context_object_name = "transactions"
    paginate_by = 50
    ordering = "-date"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_queryset(self):
        return (
            Transaction.objects
            .select_related("category", "subcategory", "payoree")
            .filter(payoree__isnull=True)  # Focus on transactions needing payoree assignment
            .order_by(self.ordering)
        )

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx    