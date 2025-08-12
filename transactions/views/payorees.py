# transactions/views/payoree.py
from django.views.generic import ListView
from django.utils.decorators import method_decorator
from transactions.models import Payoree
from transactions.utils import trace

class PayoreesListView(ListView):
    template_name = "transactions/payorees_list.html"
    context_object_name = "payorees"
    paginate_by = 100

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get_queryset(self):
        # Return a QuerySet and give it a stable ordering
        qs = Payoree.objects.all().order_by("name")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx