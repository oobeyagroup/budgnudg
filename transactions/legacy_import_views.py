# transactions/legacy_import_views.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from transactions.forms import FileUploadForm, TransactionReviewForm
from transactions.services.helpers import read_uploaded_text
from transactions.services import import_flow as imp
from transactions.utils import trace

@trace
@require_http_methods(["GET", "POST"])
def import_transactions_upload(request):
    if request.method == "POST":
        form = FileUploadForm(
            request.POST, request.FILES,
            profile_choices=request.profile_choices if hasattr(request, "profile_choices") else None,
            account_choices=None  # choices handled inside form or separate helper
        )
        if form.is_valid():
            text, name = read_uploaded_text(form.cleaned_data["file"])
            profile = form.cleaned_data["mapping_profile"]
            bank = form.cleaned_data["bank_account"]
            imp.seed_session(request.session, text=text, filename=name, profile=profile, bank=bank)
            return redirect("import_transactions_preview")
    else:
        form = FileUploadForm()

    return render(request, "transactions/import_form.html", {"form": form, "title": "Import Transactions"})

@trace
def import_transactions_preview(request):
    try:
        rows = imp.parse_preview(request.session)
    except KeyError:
        messages.error(request, "Import session missing. Please upload again.")
        return redirect("import_transactions_upload")
    return render(request, "transactions/import_transaction_preview.html", {"transactions": rows})

@trace
@require_http_methods(["GET", "POST"])
def review_transaction(request):
    row, idx, total = imp.get_current_row(request.session)
    if row is None:
        return redirect("import_transactions_confirm")

    if request.method == "POST":
        form = TransactionReviewForm(request.POST)
        if form.is_valid():
            imp.apply_review(request.session, form.cleaned_data)
            return redirect("review_transaction")
    else:
        form = TransactionReviewForm(initial=row)

    return render(request, "transactions/review_transaction.html", {"form": form, "current_index": idx + 1, "total": total})

@trace
@require_http_methods(["POST", "GET"])
def import_transactions_confirm(request):
    rows = request.session.get(imp.SESSION["parsed"], [])
    imported, duplicates, skipped = imp.persist(rows)

    if imported: messages.success(request, f"Imported {len(imported)} transactions.")
    if duplicates: messages.warning(request, f"Skipped {len(duplicates)} duplicates.")
    if skipped: messages.warning(request, f"Skipped {len(skipped)} invalid rows.")

    request.session.pop(imp.SESSION["parsed"], None)
    request.session.pop(imp.SESSION["index"], None)

    return redirect("transactions_list")