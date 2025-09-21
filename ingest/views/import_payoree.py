from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from commons.utils import trace
from django.urls import reverse
from transactions.forms import PayoreeImportForm
from transactions.services.payorees import import_payorees_from_text
from commons.services.file_processing import read_uploaded_text


class ImportPayoreeView(View):
    template_name = "ingest/import_payoree_form.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get(self, request):
        form = PayoreeImportForm()
        return render(request, self.template_name, {"form": form})

    @method_decorator(trace)
    def post(self, request):
        form = PayoreeImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        text, name = read_uploaded_text(form.cleaned_data["file"])
        try:
            stats = import_payorees_from_text(text)
        except ValueError as e:
            messages.error(request, f"Import failed: {e}")
            return render(request, self.template_name, {"form": form})

        messages.success(
            request,
            f"Payorees imported from {name}: {stats['created']} created, {stats['skipped']} skipped, {stats['rows']} rows processed.",
        )
        return redirect("transactions:payorees_list")  # or wherever you list payorees
