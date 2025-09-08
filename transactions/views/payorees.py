# transactions/views/payoree.py
from django.views.generic import ListView, UpdateView
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.shortcuts import get_object_or_404
from transactions.models import Payoree
from transactions.forms import PayoreeForm
from transactions.utils import trace
from transactions.models import RecurringSeries


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


class PayoreeEditView(UpdateView):
    """
    View for editing individual payorees with navigation controls.
    """

    model = Payoree
    form_class = PayoreeForm
    template_name = "transactions/edit_payoree.html"
    context_object_name = "payoree"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Redirect back to the payoree list after successful edit."""
        return reverse("transactions:payorees_list")

    def get_context_data(self, **kwargs):
        """Add navigation context for prev/next buttons."""
        context = super().get_context_data(**kwargs)

        # Get all payorees for navigation
        all_payorees = list(Payoree.objects.all().order_by("name"))
        current_index = None

        for i, payoree in enumerate(all_payorees):
            if payoree.id == self.object.id:
                current_index = i
                break

        if current_index is not None:
            # Previous payoree
            if current_index > 0:
                context["prev_payoree"] = all_payorees[current_index - 1]

            # Next payoree
            if current_index < len(all_payorees) - 1:
                context["next_payoree"] = all_payorees[current_index + 1]

        context.update(
            {
                "current_index": current_index + 1 if current_index is not None else 0,
                "total_payorees": len(all_payorees),
                "page_title": f"Edit Payoree - {self.object.name}",
                "page_description": "Update payoree details and default settings.",
            }
        )
        return context

    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(
            self.request, f"Payoree updated successfully: {self.object.name}"
        )
        return response

    def form_invalid(self, form):
        """Handle form validation errors."""
        messages.error(self.request, "Please correct the errors below and try again.")
        return super().form_invalid(form)


class RecurringSeriesListView(ListView):
    template_name = "transactions/recurring_series_list.html"
    context_object_name = "series_list"
    paginate_by = 100

    def get_queryset(self):
        qs = RecurringSeries.objects.filter(manually_disabled=False).order_by(
            "-last_seen"
        )
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(merchant_key__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx
