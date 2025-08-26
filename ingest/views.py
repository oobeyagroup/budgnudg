
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from transactions.utils import trace
from ingest.models import ImportBatch, MappingProfile, ScannedCheck
from ingest.forms import UploadCSVForm, AssignProfileForm, CheckUploadForm, CheckReviewForm
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch
from .services.check_ingest import save_uploaded_checks, candidate_transactions, attach_or_create_transaction

import logging

logger = logging.getLogger(__name__)

class BatchPreviewView(DetailView):
    model = ImportBatch
    template_name = "ingest/preview.html"
    context_object_name = "batch"
    http_method_names = ['get', 'post']  # Allow POST for validation
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)

    @method_decorator(trace)
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = context.get("batch")
        
        # First, try to find and assign a matching profile if none is assigned
        if batch and not batch.profile and batch.header:
            from ingest.models import MappingProfile
            profiles = MappingProfile.objects.all()
            
            # Convert batch headers to a set for comparison, filtering out None and normalizing
            batch_headers = {h.strip() for h in batch.header if h is not None and h.strip()}
            logger.debug("Looking for profile matching headers: %s", batch_headers)
            
            # Look for a profile whose column_map keys match our headers exactly
            for profile in profiles:
                # Normalize profile headers too
                profile_headers = {k.strip() for k in profile.column_map.keys() if k and k.strip()}
                logger.debug("Comparing with profile '%s' headers: %s", profile.name, profile_headers)
                
                if profile_headers == batch_headers:
                    logger.debug("Found exact matching profile: %s", profile.name)
                    batch.profile = profile
                    batch.save()
                    # Automatically apply the profile to process the data
                    updated, dup_count = apply_profile_to_batch(batch, profile)
                    messages.success(self.request, f"Automatically matched and processed with profile: {profile.name} ({updated} rows processed, {dup_count} duplicates found)")
                    break
                elif profile_headers.issubset(batch_headers):
                    # Profile headers are a subset of CSV headers (CSV has extra columns)
                    logger.debug("Found subset matching profile: %s (profile is subset of CSV)", profile.name)
                    batch.profile = profile
                    batch.save()
                    # Automatically apply the profile to process the data
                    updated, dup_count = apply_profile_to_batch(batch, profile)
                    messages.success(self.request, f"Automatically matched and processed with profile: {profile.name} ({updated} rows processed, {dup_count} duplicates found, ignoring extra CSV columns)")
                    break
        
        if not batch or not batch.profile:
            # Don't return redirect here - let the template handle the missing profile case
            context["missing_profile"] = True
            # Include CSV headers for display in the missing profile message
            if batch and batch.header:
                context["csv_headers"] = [h for h in batch.header if h is not None]
            # Include first 5 mapping profiles to show what's available
            from ingest.models import MappingProfile
            profiles = MappingProfile.objects.all()[:5]
            context["available_profiles"] = [
                {
                    "name": p.name,
                    "headers": list(p.column_map.keys()) if p.column_map else []
                }
                for p in profiles
            ]
            return context
            
        # Get field mappings from profile
        column_map = batch.profile.column_map
        # Add field mappings to context for template
        context.update({
            'date_field': next((k for k, v in column_map.items() if v == 'date'), None),
            'amount_field': next((k for k, v in column_map.items() if v == 'amount'), None),
            'description_field': next((k for k, v in column_map.items() if v == 'description'), None),
            'account_field': next((k for k, v in column_map.items() if v == 'sheet_account'), None),
            'payoree_field': next((k for k, v in column_map.items() if v == 'payoree'), None),
            'subcategory_field': next((k for k, v in column_map.items() if v == 'subcategory'), None),
            'memo_field': next((k for k, v in column_map.items() if v == 'memo'), None),
            'check_num_field': next((k for k, v in column_map.items() if v == 'check_num'), None),
        })

        # Build mapping_table for preview
        mapping_table = []
        first_row = batch.rows.first()
        txn_fields = [
            'date', 'description', 'subcategory', 'sheet_account',
            'amount', 'memo', 'payoree', 'check_num'
        ]
        for txn_field in txn_fields:
            csv_field = next((csv_f for csv_f, txn_f in column_map.items() if txn_f == txn_field), 'tbd')
            sample_value = ''
            if csv_field != 'tbd' and first_row and hasattr(first_row, 'raw'):
                sample_value = first_row.raw.get(csv_field, '')
            mapping_table.append({
                'csv_field': csv_field,
                'sample_value': sample_value,
                'txn_field': txn_field
            })
        mapping_table.append({
            'csv_field': 'filename',
            'sample_value': batch.source_filename,
            'txn_field': 'source'
        })
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
    profile = get_object_or_404(MappingProfile, pk=profile_id)
    updated, dup_count = apply_profile_to_batch(batch, profile, bank_account_hint=request.POST.get("bank_account"))
    batch.refresh_from_db()
    messages.success(request, f"Mapped {updated} rows. Duplicates flagged: {dup_count}.")
    return redirect("ingest:batch_preview", pk=batch.id)

@trace
def commit(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    
    if request.method == "POST":
        bank_account = request.POST.get("bank_account")
        if not bank_account:
            messages.error(request, "Bank account is required.")
            return redirect("ingest:batch_preview", pk=batch.pk)
        
        logger.debug("Committing batch %s with bank_account: %s", batch.pk, bank_account)
        imported, dups, skipped = commit_batch(batch, bank_account)
        messages.success(request, f"Imported {len(imported)} transactions; skipped {len(skipped)} (duplicates: {len(dups)}).")
        return redirect("transactions:transactions_list")
    else:
        # If GET request, redirect back to preview
        return redirect("ingest:batch_preview", pk=batch.pk)

class BatchListView(ListView):
    model = ImportBatch
    template_name = "ingest/batch_list.html"
    context_object_name = "batches"
    paginate_by = 20


class MappingProfileListView(ListView):
    model = MappingProfile
    template_name = "ingest/profile_list.html"
    context_object_name = "profiles"
    paginate_by = 20


class MappingProfileDetailView(DetailView):
    model = MappingProfile
    template_name = "ingest/profile_detail.html"
    context_object_name = "profile"

# ingest/views.py (check_upload)
@require_http_methods(["GET", "POST"])
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
        return redirect("ingest:check_upload")

    # GET
    form = CheckUploadForm()
    return render(request, "ingest/check_upload.html", {"form": form})

@require_http_methods(["GET", "POST"])
def check_review(request, pk: int):
    sc = get_object_or_404(ScannedCheck, pk=pk)
    initial = {
        "bank_account": sc.bank_account or "",
        "check_number": sc.check_number or "",
        "date": sc.date,
        "amount": sc.amount,
        "payoree": sc.payoree_id,
        "memo_text": sc.memo_text or "",
    }
    form = CheckReviewForm(request.POST or None, initial=initial)

    candidates = []
    if request.method == "POST" and form.is_valid():
        cleaned = form.cleaned_data
        # discover candidates for this submission (use posted values)
        candidates = candidate_transactions(
            cleaned["bank_account"], cleaned["date"], cleaned["amount"], cleaned.get("check_number")
        )

        # If the user selected a candidate (via hidden/radio in template), attach immediately
        if cleaned.get("match_txn_id"):
            attach_or_create_transaction(sc, cleaned)
            messages.success(request, "Image linked to existing transaction.")
            return _redirect_to_next_unresolved()

        # else we’ll show candidates and let them confirm create or select
        # If user clicked “Create new now”, you can branch on a form button name
        if "create_new" in request.POST:
            attach_or_create_transaction(sc, cleaned)
            messages.success(request, "New transaction created from check image.")
            return _redirect_to_next_unresolved()
    else:
        # compute candidates off initial to pre-show
        if initial["bank_account"] and initial["date"] and initial["amount"] is not None:
            candidates = candidate_transactions(
                initial["bank_account"], initial["date"], initial["amount"], initial["check_number"]
            )

    return render(request, "transactions/check_review.html", {
        "form": form,
        "sc": sc,
        "candidates": candidates,
    })

def _redirect_to_next_unresolved():
    nxt = ScannedCheck.objects.filter(transaction__isnull=True).order_by("created_at").first()
    if nxt:
        return redirect("transactions:check_review", pk=nxt.pk)
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

@trace
@require_POST
def match_check(request):
    check_id = request.POST.get("check_id")
    txn_id = request.POST.get("txn_id")
    payee = request.POST.get("payee") or ""
    memo = request.POST.get("memo") or ""

    check = get_object_or_404(ScannedCheck, pk=check_id)
    txn = get_object_or_404(Transaction, pk=txn_id)

    with dbtx.atomic():
        # link
        check.matched_transaction = txn
        check.save(update_fields=["matched_transaction"])

        # optionally set payee/memo on the txn if missing
        updates = []
        if payee and not getattr(txn, "payoree", None):
            # if you have a Payoree model with a helper:
            from transactions.models import Payoree
            pyo = Payoree.get_existing(payee) or Payoree.objects.create(name=payee)
            txn.payoree = pyo
            updates.append("payoree")
        if memo and not txn.memo:
            txn.memo = memo
            updates.append("memo")
        if updates:
            txn.save(update_fields=updates)

    messages.success(request, f"Matched check {check.check_number} to txn {txn.pk}.")
    return redirect("transactions:checks_reconcile")

@trace
@require_POST
def unlink_check(request, check_id: int):
    check = get_object_or_404(ScannedCheck, pk=check_id)
    check.matched_transaction = None
    check.save(update_fields=["matched_transaction"])
    messages.info(request, f"Unlinked check {check.check_number}.")
    return redirect("transactions:checks_reconcile")