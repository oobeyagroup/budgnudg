# transactions/views/dashboard.py
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from transactions.selectors import account_summary, recent_transactions
from transactions.utils import trace  # your function decorator



class DashboardView(TemplateView):
    template_name = "transactions/dashboard_home.html"

    # trace every request to this CBV
    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["accounts"] = account_summary()
        ctx["transactions"] = recent_transactions(limit=50)
        return ctx