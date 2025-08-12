from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from transactions.utils import trace
from django.urls import reverse
# from transactions.forms import PayoreeImportForm
# from transactions.services.payorees import import_payorees_from_text
# from transactions.services.helpers import read_uploaded_text

class ImportPayoreeView(View):
    template_name = "transactions/import_payoree_form.html"

    @method_decorator(trace)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @method_decorator(trace)
    def get(self, request):
        # form = PayoreeImportForm()
        return render(request, self.template_name, {"form": None})

    @method_decorator(trace)
    def post(self, request):
        # form = PayoreeImportForm(request.POST, request.FILES)
        # if not form.is_valid():
        #     return render(request, self.template_name, {"form": form})
        # text, name = read_uploaded_text(form.cleaned_data["file"])
        # stats = import_payorees_from_text(text)
        messages.success(request, "Payoree import complete.")
        return redirect("payorees_list")  # or wherever you list payorees