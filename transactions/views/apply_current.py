from django.views import View
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.decorators import method_decorator
from transactions.models import Transaction
from transactions.utils import trace

class ApplyCurrentToSimilarView(View):
    """
    Path: apply_current/<int:transaction_id>/
    Name: apply_current_to_similar
    """

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def post(self, request, transaction_id):
        txn = get_object_or_404(Transaction, pk=transaction_id)
        # TODO: find similar transactions and apply current subcategory/payoree
        return HttpResponseRedirect(reverse("transactions_list"))

    @method_decorator(trace)
    def get(self, request, transaction_id):
        return self.post(request, transaction_id)