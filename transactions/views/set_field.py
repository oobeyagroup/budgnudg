from django.views import View
from django.http import HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from transactions.models import Transaction, Category, Payoree
from transactions.utils import trace

class SetTransactionFieldView(View):
    """
    Path: set/<int:transaction_id>/<str:field>/<int:value_id>/
    Name: set_transaction_field
    """

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def post(self, request, transaction_id, field, value_id):
        txn = get_object_or_404(Transaction, pk=transaction_id)

        if field == "subcategory":
            obj = get_object_or_404(Category, pk=value_id)
            txn.subcategory = obj
        elif field == "payoree":
            obj = get_object_or_404(Payoree, pk=value_id)
            txn.payoree = obj
        else:
            return HttpResponseBadRequest("Unsupported field")

        txn.save(update_fields=[field])
        return HttpResponseRedirect(reverse("transactions_list"))

    # if your old route used GET, keep this too:
    @method_decorator(trace)
    def get(self, request, transaction_id, field, value_id):
        return self.post(request, transaction_id, field, value_id)