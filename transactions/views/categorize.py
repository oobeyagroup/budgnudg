# transactions/views/categorize.py
from django.views import View
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from transactions.models import Transaction
from transactions.utils import trace

class CategorizeTransactionView(View):
    template_name = "transactions/categorize_transaction.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get(self, request, pk):
        txn = get_object_or_404(Transaction, pk=pk)
        ctx = {"txn": txn}  # TODO: add form
        return render(request, self.template_name, ctx)

    @method_decorator(trace)
    def post(self, request, pk):
        txn = get_object_or_404(Transaction, pk=pk)
        # TODO: validate & save form
        messages.success(request, "Transaction updated.")
        return redirect("transactions_list")