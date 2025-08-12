from django.views.generic import ListView
from django.db.models import Count
from django.utils.decorators import method_decorator
from transactions.models import Transaction
from transactions.utils import trace

class BankAccountsListView(ListView):
    template_name = "transactions/bank_accounts_list.html"
    context_object_name = "accounts"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_queryset(self):
        return (
            Transaction.objects
            .exclude(bank_account__isnull=True)
            .exclude(bank_account__exact="")
            .values("bank_account")
            .annotate(txn_count=Count("id"))
            .order_by("bank_account")
        )

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx