# transactions/views/import_flow.py
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from transactions.utils import trace
import logging
from .mixins import ImportSessionMixin
from transactions.forms import TransactionImportForm, TransactionReviewForm

from transactions.services.mapping import map_file_for_profile
from transactions.services.suggestions import apply_suggestions
from transactions.services.duplicates import find_duplicates


logger = logging.getLogger(__name__)

class ImportUploadView(ImportSessionMixin, View):
    template_name = "transactions/import_form.html"

    @method_decorator(trace)
    def get(self, request):
        form = TransactionImportForm(
            profile_choices=self.profile_choices(),
            account_choices=self.account_choices(),
        )
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        form = TransactionImportForm(
            request.POST,
            request.FILES,
            profile_choices=self.profile_choices(),
            account_choices=self.account_choices(),
        )
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        # Save upload + selections into session
        self.save_upload_to_session(request, form)
        return redirect("import_transactions_preview")


class ImportPreviewView(ImportSessionMixin, View):
    template_name = "transactions/import_transaction_preview.html"
    @method_decorator(trace)
    def get(self, request):
        # pull upload state from session
        try:
            file_text, profile_name, bank = self.read_session_upload(request)
        except KeyError:
            return redirect("import_transactions_upload")

        # map CSV -> model-shaped dicts
        rows = map_file_for_profile(file_text, profile_name, bank)
        # suggestions + duplicate flags
        rows = apply_suggestions(rows)
        rows = find_duplicates(rows)
        if rows:
            logger.debug("First mapped row: %s", rows[0])

        # persist rows in session for review/confirm
        self.save_parsed(request, rows)

        return render(request, self.template_name, {"transactions": rows})


class ReviewTransactionView(ImportSessionMixin, View):

    template_name = "transactions/review_transaction.html"

    @method_decorator(trace)
    def get(self, request):
        txn, idx, total = self.current_row(request)
        if txn is None:
            # finished reviewing → go to confirm page
            return redirect("import_transactions_preview")  # or 'import_transactions_confirm'
        form = TransactionReviewForm(initial=txn)
        return render(
            request,
            self.template_name,
            {"form": form, "current_index": idx + 1, "total": total},
        )
    @method_decorator(trace)
    def post(self, request):
        form = TransactionReviewForm(request.POST)
        if not form.is_valid():
            txn, idx, total = self.current_row(request)
            return render(
                request,
                self.template_name,
                {"form": form, "current_index": idx + 1, "total": total},
            )

        # merge edits back into the session row, advance pointer
        self.apply_review(request, form.cleaned_data)
        return redirect("review_transaction")


class ImportConfirmView(ImportSessionMixin, View):
    @method_decorator(trace)
    def post(self, request):
        rows = self.get_parsed(request)
        imported, duplicates, skipped = self.persist_rows(rows)

        if imported:
            messages.success(request, f"Imported {len(imported)} transactions.")
        if duplicates:
            messages.warning(request, f"Skipped {len(duplicates)} duplicates.")
        if skipped:
            messages.warning(request, f"Skipped {len(skipped)} invalid rows.")

        # Optional: clear parsed rows so refresh can’t re-import
        request.session.pop("parsed_transactions", None)
        request.session.pop("review_index", None)

        # Reuse your list page or dashboard
        return redirect("transactions_list")  # or 'dashboard'