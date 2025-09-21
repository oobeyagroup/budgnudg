# ingest/views/import_categories.py
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse

from transactions.forms import CategoryImportForm
from commons.services.file_processing import read_uploaded_text
from transactions.services.categories import import_categories_from_text
from commons.utils import trace  # your function decorator


class ImportCategoriesView(View):
    template_name = "ingest/import_categories_form.html"

    @method_decorator(trace)
    def get(self, request):
        return render(request, self.template_name, {"form": CategoryImportForm()})

    def post(self, request):
        form = CategoryImportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        text, name = read_uploaded_text(form.cleaned_data["file"])
        try:
            stats = import_categories_from_text(text)
        except ValueError as e:
            messages.error(request, f"Import failed: {e}")
            return render(request, self.template_name, {"form": form})

        messages.success(
            request,
            f"Categories imported from {name}: {stats['created']} created, {stats['rows']} rows processed.",
        )
        return redirect("transactions:categories_list")  # reuse your existing page
