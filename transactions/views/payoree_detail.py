from django.views.generic import TemplateView
from django.shortcuts import get_object_or_404
from transactions.models import Payoree, Transaction

class PayoreeDetailView(TemplateView):
    template_name = "transactions/payoree_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payoree_id = self.kwargs.get("pk")
        payoree = get_object_or_404(Payoree, pk=payoree_id)
        transactions = Transaction.objects.filter(payoree=payoree).order_by("-date")
        context["payoree"] = payoree
        context["transactions"] = transactions
        return context
