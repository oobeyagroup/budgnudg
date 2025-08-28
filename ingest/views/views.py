from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction as dbtx
from transactions.utils import trace
from transactions.models import Transaction, Payoree, Category
from ingest.models import ImportBatch, FinancialAccount, ScannedCheck
from ingest.forms import (
    UploadCSVForm,
    CheckUploadForm,
    TransactionQuickEditForm
)
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch
from ..services.check_ingest import (
    save_uploaded_checks,
    candidate_transactions,
    attach_or_create_transaction,
)
from ..services.matching import find_candidates, render_description
from django.http import HttpResponse
from django.db.models import Q


import logging

logger = logging.getLogger(__name__)


class BatchPreviewView(DetailView):
    model = ImportBatch
    template_name = "ingest/preview.html"
    context_object_name = "batch"
    http_method_names = ["get", "post"]  # Allow POST for validation

    @method_decorator(trace)
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = context.get("batch")

        # First, try to find and assign a matching profile if none is assigned
        if batch and not batch.profile and batch.header:
            from ingest.models import FinancialAccount

            profiles = FinancialAccount.objects.all()

            # Convert batch headers to a set for comparison, filtering out None and normalizing
            batch_headers = {
                h.strip() for h in batch.header if h is not None and h.strip()
            }
            logger.debug("Looking for profile matching headers: %s", batch_headers)

            # Look for a profile whose column_map keys match our headers exactly
            for profile in profiles:
                # Normalize profile headers too
                profile_headers = {
                    k.strip() for k in profile.column_map.keys() if k and k.strip()
                }
                logger.debug(
                    "Comparing with profile '%s' headers: %s",
                    profile.name,
                    profile_headers,
                )

                if profile_headers == batch_headers:
                    logger.debug("Found exact matching profile: %s", profile.name)
                    batch.profile = profile
                    batch.save()
                    # Automatically apply the profile to process the data
                    updated, dup_count = apply_profile_to_batch(batch, profile)
                    messages.success(
                        self.request,
                        f"Automatically matched and processed with profile: {profile.name} ({updated} rows processed, {dup_count} duplicates found)",
                    )
                    break
                elif profile_headers.issubset(batch_headers):
                    # Profile headers are a subset of CSV headers (CSV has extra columns)
                    logger.debug(
                        "Found subset matching profile: %s (profile is subset of CSV)",
                        profile.name,
                    )
                    batch.profile = profile
                    batch.save()
                    # Automatically apply the profile to process the data
                    updated, dup_count = apply_profile_to_batch(batch, profile)
                    messages.success(
                        self.request,
                        f"Automatically matched and processed with profile: {profile.name} ({updated} rows processed, {dup_count} duplicates found, ignoring extra CSV columns)",
                    )
                    break

        if not batch or not batch.profile:
            # Don't return redirect here - let the template handle the missing profile case
            context["missing_profile"] = True
            # Include CSV headers for display in the missing profile message
            if batch and batch.header:
                context["csv_headers"] = [h for h in batch.header if h is not None]
            # Include first 5 mapping profiles to show what's available
            from ingest.models import FinancialAccount

            profiles = FinancialAccount.objects.all()[:5]
            context["available_profiles"] = [
                {
                    "name": p.name,
                    "headers": list(p.column_map.keys()) if p.column_map else [],
                }
                for p in profiles
            ]
            return context

        # Get field mappings from profile
        column_map = batch.profile.column_map
        # Add field mappings to context for template
        context.update(
            {
                "date_field": next(
                    (k for k, v in column_map.items() if v == "date"), None
                ),
                "amount_field": next(
                    (k for k, v in column_map.items() if v == "amount"), None
                ),
                "description_field": next(
                    (k for k, v in column_map.items() if v == "description"), None
                ),
                "account_field": next(
                    (k for k, v in column_map.items() if v == "sheet_account"), None
                ),
                "payoree_field": next(
                    (k for k, v in column_map.items() if v == "payoree"), None
                ),
                "subcategory_field": next(
                    (k for k, v in column_map.items() if v == "subcategory"), None
                ),
                "memo_field": next(
                    (k for k, v in column_map.items() if v == "memo"), None
                ),
                "check_num_field": next(
                    (k for k, v in column_map.items() if v == "check_num"), None
                ),
            }
        )

        # Build mapping_table for preview
        mapping_table = []
        first_row = batch.rows.first()
        txn_fields = [
            "date",
            "description",
            "subcategory",
            "sheet_account",
            "amount",
            "memo",
            "payoree",
            "check_num",
        ]
        for txn_field in txn_fields:
            csv_field = next(
                (csv_f for csv_f, txn_f in column_map.items() if txn_f == txn_field),
                "tbd",
            )
            sample_value = ""
            if csv_field != "tbd" and first_row and hasattr(first_row, "raw"):
                sample_value = first_row.raw.get(csv_field, "")
            mapping_table.append(
                {
                    "csv_field": csv_field,
                    "sample_value": sample_value,
                    "txn_field": txn_field,
                }
            )
        mapping_table.append(
            {
                "csv_field": "filename",
                "sample_value": batch.source_filename,
                "txn_field": "source",
            }
        )
        context["mapping_table"] = mapping_table

        # Add profile to context explicitly for template access
        context["profile"] = batch.profile

        return context


@trace
def upload_csv(request):
    if request.method == "POST":
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            batch = create_batch_from_csv(
                request.FILES["file"],
                user=request.user if request.user.is_authenticated else None,
                profile=form.cleaned_data.get("profile"),
            )
            messages.success(request, f"Uploaded {batch.row_count} rows.")
            return redirect("ingest:batch_preview", pk=batch.pk)
    else:
        form = UploadCSVForm()
    return render(request, "ingest/upload_form.html", {"form": form})


@trace
def apply_profile(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    profile_id = request.POST.get("profile_id")
    logger.debug("Received profile_id=%s", profile_id)  # Debug log
    profile = get_object_or_404(FinancialAccount, pk=profile_id)
    updated, dup_count = apply_profile_to_batch(
        batch, profile, bank_account_hint=request.POST.get("bank_account")
    )
    batch.refresh_from_db()
    messages.success(
        request, f"Mapped {updated} rows. Duplicates flagged: {dup_count}."
    )
    return redirect("ingest:batch_preview", pk=batch.id)


@trace
def commit(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)

    if request.method == "POST":
        bank_account = request.POST.get("bank_account")
        if not bank_account:
            messages.error(request, "Bank account is required.")
            return redirect("ingest:batch_preview", pk=batch.pk)

        logger.debug(
            "Committing batch %s with bank_account: %s", batch.pk, bank_account
        )
        imported, dups, skipped = commit_batch(batch, bank_account)
        messages.success(
            request,
            f"Imported {len(imported)} transactions; skipped {len(skipped)} (duplicates: {len(dups)}).",
        )
        return redirect("transactions:transactions_list")
    else:
        # If GET request, redirect back to preview
        return redirect("ingest:batch_preview", pk=batch.pk)


class BatchListView(ListView):
    model = ImportBatch
    template_name = "ingest/batch_list.html"
    context_object_name = "batches"
    paginate_by = 20


class FinancialAccountListView(ListView):
    model = FinancialAccount
    template_name = "ingest/profile_list.html"
    context_object_name = "profiles"
    paginate_by = 20


class FinancialAccountDetailView(DetailView):
    model = FinancialAccount
    template_name = "ingest/profile_detail.html"
    context_object_name = "profile"


@require_http_methods(["GET", "POST"])
@trace
def check_upload(request):
    if request.method == "POST":
        logger.debug("FILES keys: %s", list(request.FILES.keys()))
        form = CheckUploadForm(request.POST, request.FILES)
        logger.debug("Form is_valid? %s", form.is_valid())
        if not form.is_valid():
            logger.debug("Form errors: %s", form.errors)
            return render(request, "ingest/check_upload.html", {"form": form})

        files = form.cleaned_data["images"]  # <-- list[UploadedFile]
        logger.debug("Got %d files: %s", len(files), [f.name for f in files])

        if not files:
            messages.error(request, "Please select at least one image.")
            return render(request, "ingest/check_upload.html", {"form": form})

        created, skipped = save_uploaded_checks(files)
        if created:
            messages.success(request, f"Uploaded {len(created)} image(s).")
        if skipped:
            messages.warning(request, f"Skipped {len(skipped)} duplicate image(s).")
        return redirect("ingest:scannedcheck_list")

    # GET
    form = CheckUploadForm()
    return render(request, "ingest/check_upload.html", {"form": form})


@trace
def _redirect_to_next_unresolved():
    nxt = (
        ScannedCheck.objects.filter(transaction__isnull=True)
        .order_by("created_at")
        .first()
    )
    if nxt:
        return redirect("ingest:match_check", pk=nxt.pk)
    return redirect("transactions:transactions_list")

@trace
def check_reconcile(request):
    account = request.GET.get("account") or ""
    txns = check_like_transactions(account=account)
    checks = ScannedCheck.objects.filter(matched_transaction__isnull=True)
    context = {
        "account": account,
        "transactions": txns,
        "checks": checks.order_by("-date", "-id"),
    }
    return render(request, "transactions/checks_reconcile.html", context)

@require_POST
@trace
def unlink_check(request, check_id: int):
    check = get_object_or_404(ScannedCheck, pk=check_id)
    check.linked_transaction = None
    check.save(update_fields=["linked_transaction"])
    messages.info(request, f"Unlinked check {check.check_number}.")
    return redirect("ingest:scannedcheck_list")


class ScannedCheckListView(ListView):
    model = ScannedCheck
    template_name = "ingest/check_list.html"
    context_object_name = "checks"
    paginate_by = 50

    @method_decorator(trace)
    def get_queryset(self):
        qs = ScannedCheck.objects.all().order_by("-created_at")
        q = (self.request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(original_filename__icontains=q)
                | Q(bank_account__icontains=q)
                | Q(check_number__icontains=q)
                | Q(payoree__name__icontains=q)  # if you have FK to Payoree
                | Q(memo_text__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["q"] = self.request.GET.get("q", "")
        return ctx


@trace
def txn_edit_partial(request, pk):
    txn = get_object_or_404(Transaction, pk=pk)
    check_id = request.GET.get("check_id") or request.POST.get("link_scanned_check_id")
    check = get_object_or_404(ScannedCheck, pk=check_id) if check_id else None

    if request.method == "POST":
        form = TransactionQuickEditForm(request.POST, instance=txn)
        if form.is_valid():
            obj = form.save()
            # link the scanned check to this transaction (adjust fields as per your model)
            if check:
                check.linked_transaction = obj
                check.bank_account = obj.bank_account or check.bank_account
                check.check_number = check.check_number or _extract_check_num(
                    obj.description
                )
                check.amount = check.amount or obj.amount
                check.save(
                    update_fields=[
                        "linked_transaction",
                        "bank_account",
                        "check_number",
                        "amount",
                    ]
                )
            return render(
                request, "ingest/_txn_edit_cancel.html"
            )  # collapse panel back to “Pick Select…”
    else:
        form = TransactionQuickEditForm(instance=txn)

    return render(
        request,
        "ingest/_txn_edit_form.html",
        {"form": form, "txn": txn, "check": check},
    )


@trace
def txn_edit_cancel(request):
    return render(request, "ingest/_txn_edit_cancel.html")


@trace
def _extract_check_num(desc: str | None) -> str:
    if not desc:
        return ""
    # naive pull like "CHECK 1234"
    import re

    m = re.search(r"\b(?:CHECK|CHK)\s*(\d{3,6})\b", desc.upper())
    return m.group(1) if m else ""

