from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction as dbtx
from transactions.utils import trace
from transactions.models import Transaction, Payoree
from ingest.models import ImportBatch, MappingProfile, ScannedCheck
from ingest.forms import (
    UploadCSVForm,
    AssignProfileForm,
    CheckUploadForm,
    CheckReviewForm,
    BankPickForm,
    AttachCheckForm,
    TransactionQuickEditForm,
    AttachEditForm,
    CreateNewTransactionForm,
)
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch
from .services.check_ingest import (
    save_uploaded_checks,
    candidate_transactions,
    attach_or_create_transaction,
)
from .services.matching import find_candidates, render_description
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
            from ingest.models import MappingProfile

            profiles = MappingProfile.objects.all()

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
            from ingest.models import MappingProfile

            profiles = MappingProfile.objects.all()[:5]
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
    profile = get_object_or_404(MappingProfile, pk=profile_id)
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


class MappingProfileListView(ListView):
    model = MappingProfile
    template_name = "ingest/profile_list.html"
    context_object_name = "profiles"
    paginate_by = 20


class MappingProfileDetailView(DetailView):
    model = MappingProfile
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


@require_http_methods(["GET", "POST"])
@trace
def check_review_old(request, pk: int):
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
            cleaned["bank_account"],
            cleaned["date"],
            cleaned["amount"],
            cleaned.get("check_number"),
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
        if (
            initial["bank_account"]
            and initial["date"]
            and initial["amount"] is not None
        ):
            candidates = candidate_transactions(
                initial["bank_account"],
                initial["date"],
                initial["amount"],
                initial["check_number"],
            )

    # figure out prev/next among unresolved checks (or all checks if you prefer)
    unresolved_ids = list(
        ScannedCheck.objects.filter(transaction__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)
    )
    try:
        i = unresolved_ids.index(sc.id)
    except ValueError:
        i = -1

    prev_id = unresolved_ids[i - 1] if i > 0 else None
    next_id = unresolved_ids[i + 1] if i != -1 and i + 1 < len(unresolved_ids) else None

    prev_url = reverse("ingest:check_review", args=[prev_id]) if prev_id else None
    next_url = reverse("ingest:check_review", args=[next_id]) if next_id else None
    cancel_url = reverse("ingest:scannedcheck_list")

    context = {
        "sc": sc,
        "form": form,
        "prev_url": reverse("ingest:check_review", args=[prev_id]) if prev_id else None,
        "next_url": reverse("ingest:check_review", args=[next_id]) if next_id else None,
        "cancel_url": reverse("ingest:scannedcheck_list"),  # or any route you prefer
    }
    return render(request, "ingest/check_review.html", context)


@trace
def _redirect_to_next_unresolved():
    nxt = (
        ScannedCheck.objects.filter(transaction__isnull=True)
        .order_by("created_at")
        .first()
    )
    if nxt:
        return redirect("ingest:check_review", pk=nxt.pk)
    return redirect("transactions:transactions_list")


@require_http_methods(["GET", "POST"])
@trace
def check_review(request, pk: int):
    sc = get_object_or_404(ScannedCheck, pk=pk)

    # If POST and user selected to add a new payoree, create it and update POST data
    post_data = request.POST.copy() if request.method == "POST" else None
    if request.method == "POST":
        payoree_val = post_data.get("payoree")
        new_payoree_name = post_data.get("new_payoree", "").strip()
        if payoree_val == "__new__" and new_payoree_name:
            # Create new payoree
            from transactions.models import Payoree

            payoree_obj, _ = Payoree.objects.get_or_create(name=new_payoree_name)
            post_data["payoree"] = str(payoree_obj.id)
    # Form bound to the instance for both GET and POST
    form = CheckReviewForm(post_data or None, instance=sc)

    # pick bank account (query param)
    bank = request.GET.get("bank") or ""
    # get list of known bank accounts (distinct from transactions)
    bank_accounts = (
        Transaction.objects.exclude(bank_account__isnull=True)
        .exclude(bank_account__exact="")
        .values_list("bank_account", flat=True)
        .distinct()
        .order_by("bank_account")
    )

    # Handle bank selection submit (separate from the ModelForm submit)
    if request.method == "POST" and "pick_bank" in request.POST:
        picked = (request.POST.get("bank_account") or "").strip()
        if picked:
            # persist the choice on the ScannedCheck
            ScannedCheck.objects.filter(pk=sc.pk).update(bank_account=picked)
            # reflect selection in querystring so template shows it selected
            return redirect(
                f"{reverse('ingest:check_review', args=[sc.pk])}?bank={picked}"
            )

    # Build prev/next among unresolved (or all, if you prefer)
    unresolved_ids = list(
        ScannedCheck.objects.filter(linked_transaction__isnull=True)
        .order_by("created_at")
        .values_list("id", flat=True)
    )
    try:
        i = unresolved_ids.index(sc.id)
    except ValueError:
        i = -1

    prev_id = unresolved_ids[i - 1] if i > 0 else None
    next_id = unresolved_ids[i + 1] if i != -1 and i + 1 < len(unresolved_ids) else None

    prev_url = reverse("ingest:check_review", args=[prev_id]) if prev_id else None
    next_url = reverse("ingest:check_review", args=[next_id]) if next_id else None
    cancel_url = reverse("ingest:scannedcheck_list")  # make sure this URL name exists

    if request.method == "POST":
        if form.is_valid():
            form.save()  # <-- persist changes to ScannedCheck
            messages.success(request, "Check saved.")

            # Navigate if user clicked a nav button
            if "next" in request.POST and next_url:
                return redirect(next_url)
            if "prev" in request.POST and prev_url:
                return redirect(prev_url)
            if "cancel" in request.POST:
                return redirect(cancel_url)

            # Default after save: stay on the page
            return redirect(reverse("ingest:check_review", args=[sc.pk]))
        else:
            messages.error(request, "Please fix the errors below.")

    # For payoree assignment partial
    payorees = form.fields["payoree"].queryset if "payoree" in form.fields else []
    payoree_matches = []  # You can add logic for suggestions if desired
    return render(
        request,
        "ingest/check_review.html",
        {
            "sc": sc,
            "form": form,
            "prev_url": prev_url,
            "next_url": next_url,
            "cancel_url": cancel_url,
            "bank": bank,
            "bank_accounts": bank_accounts,
            "payorees": payorees,
            "payoree_matches": payoree_matches,
        },
    )


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
    return redirect("ingest:checks_reconcile")

@trace
@require_POST
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
def review_scanned_check(request, pk: int):
    """
    Step 1: pick bank account (from existing Transactions)
    Step 2: show candidates: transactions with that bank, "CHECK" in description, no payoree
    Step 3: attach: copy fields from ScannedCheck into the chosen Transaction (if missing),
            and record linkage (optional) on the ScannedCheck
    """
    check = get_object_or_404(ScannedCheck, pk=pk)

    # --- Step 1: bank selection (GET or POST with bank pick) ---
    bank = request.GET.get("bank") or None
    bank_form = BankPickForm(
        data=request.POST or None, initial={"bank_account": check.bank_account or bank}
    )

    # Handle bank selection submit
    if request.method == "POST" and "pick_bank" in request.POST:
        if bank_form.is_valid():
            bank = bank_form.cleaned_data["bank_account"]
            # Persist on the check so refresh remembers it
            ScannedCheck.objects.filter(pk=check.pk).update(bank_account=bank)
            return redirect(
                f"{reverse('ingest:scannedcheck_review', args=[check.pk])}?bank={bank}"
            )

    # If we don’t have a bank yet, render only the picker + image
    if not bank:
        return render(
            request,
            "ingest/review_scanned_check.html",
            {
                "check": check,
                "bank_form": bank_form,
                "candidates": [],
            },
        )

    # --- Step 2: candidate query ---
    candidates = Transaction.objects.filter(
        bank_account=bank, description__icontains="CHECK"
    ).order_by("-date")[:100]

    # --- Step 3: attach check to a chosen transaction ---
    attach_form = AttachCheckForm(data=request.POST or None)
    if request.method == "POST" and "attach" in request.POST and attach_form.is_valid():
        txn_id = attach_form.cleaned_data["transaction_id"]
        txn = get_object_or_404(Transaction, pk=txn_id)

        with dbtx.atomic():
            # Update transaction with info from the scanned check, only when empty
            if not txn.payoree and check.payoree:
                txn.payoree = check.payoree
            if not txn.subcategory and getattr(check, "suggested_subcategory", None):
                txn.subcategory = (
                    check.suggested_subcategory
                )  # if you later add this field
            if (txn.memo or "").strip() == "" and (check.memo_text or "").strip():
                txn.memo = check.memo_text

            # Don’t blindly overwrite date/amount; only fill if missing
            if not txn.date and check.date:
                txn.date = check.date
            if not txn.amount and check.amount:
                txn.amount = check.amount

            txn.save()

            # Optional: link the check to the transaction if your model has such a field
            if hasattr(check, "linked_transaction_id"):
                check.linked_transaction = txn
                check.save(update_fields=["linked_transaction"])

        messages.success(request, f"Attached check to transaction #{txn.id}.")
        return redirect(
            reverse("ingest:scannedcheck_review", args=[check.pk]) + f"?bank={bank}"
        )

    return render(
        request,
        "ingest/review_scanned_check.html",
        {
            "check": check,
            "bank_form": bank_form,
            "candidates": candidates,
            "attach_form": attach_form,
            "selected_bank": bank,
        },
    )


@trace
def review_scanned_check(request, pk):
    check = get_object_or_404(ScannedCheck, pk=pk)
    # pick bank account (query param)
    bank = request.GET.get("bank") or ""
    # get list of known bank accounts (distinct from transactions)
    bank_accounts = (
        Transaction.objects.exclude(bank_account__isnull=True)
        .exclude(bank_account__exact="")
        .values_list("bank_account", flat=True)
        .distinct()
        .order_by("bank_account")
    )

    candidates = Transaction.objects.none()
    if bank:
        candidates = (
            Transaction.objects.filter(bank_account=bank)
            .filter(Q(description__icontains="CHECK") | Q(description__icontains="CHK"))
            .filter(payoree__isnull=True)
            .order_by("-date")[:200]
        )

    return render(
        request,
        "ingest/scannedcheck_review.html",
        {
            "check": check,
            "bank": bank,
            "bank_accounts": bank_accounts,
            "candidates": candidates,
        },
    )


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


def _existing_bank_accounts() -> list[str]:
    from transactions.models import Transaction

    return list(
        Transaction.objects.exclude(bank_account__exact="")
        .values_list("bank_account", flat=True)
        .distinct()
    )


@require_http_methods(["GET", "POST"])
def match_check(request, pk: int):
    sc = get_object_or_404(ScannedCheck, pk=pk)

    # 1) Bank selection gate
    bank = request.GET.get("bank") or sc.bank_account or ""
    bank_form = BankPickForm(
        request.POST or None,
        accounts=_existing_bank_accounts(),
        initial={"bank_account": bank or ""},
    )
    if request.method == "POST" and "pick_bank" in request.POST:
        if bank_form.is_valid():
            bank = bank_form.cleaned_data["bank_account"]
            ScannedCheck.objects.filter(pk=sc.pk).update(bank_account=bank)
            return redirect(
                f"{reverse('ingest:match_check', args=[sc.pk])}?bank={bank}"
            )

    if not bank:
        return render(
            request,
            "ingest/match_check.html",
            {
                "sc": sc,
                "bank_form": bank_form,
                "candidates": [],
                "selected": None,
                "desc_preview": "",
                "why": [],
            },
        )

    # 2) Candidate list (scored)
    cands = find_candidates(
        bank=bank,
        check_no=sc.check_number or "",
        amount=sc.amount,
    )
    top = cands[0] if cands else None
    top_txn = top.txn if top else None
    why = top.why if top else []

    # 3) POST: attach to existing
    if request.method == "POST" and "attach_save" in request.POST:
        form = AttachEditForm(request.POST)
        if form.is_valid():
            txn = get_object_or_404(Transaction, pk=form.cleaned_data["transaction_id"])
            # Compose description using template
            new_desc = render_description(
                csv_desc=txn.description or "",
                check_no=sc.check_number or None,
                payoree=(
                    form.cleaned_data["payoree"].name
                    if form.cleaned_data["payoree"]
                    else None
                ),
                memo=form.cleaned_data["memo_text"] or None,
            )
            # Update transaction fields
            if form.cleaned_data["payoree"]:
                txn.payoree = form.cleaned_data["payoree"]
            if form.cleaned_data.get("subcategory_id"):
                sub = Category.objects.filter(
                    pk=form.cleaned_data["subcategory_id"]
                ).first()
                if sub:
                    txn.subcategory = sub
            if form.cleaned_data.get("set_account_type_check"):
                txn.account_type = "Check"  # or your canonical value
            txn.description = new_desc
            if sc.bank_account and not txn.bank_account:
                txn.bank_account = sc.bank_account
            txn.save()

            # Link + status
            sc.linked_transaction = txn
            sc.status = "confirmed"
            sc.save(update_fields=["linked_transaction", "status"])

            messages.success(
                request, f"Attached check #{sc.check_number or ''} to T-{txn.pk}."
            )
            # Next workflow: go to next unmatched
            nxt = (
                ScannedCheck.objects.filter(status="unmatched")
                .exclude(pk=sc.pk)
                .order_by("id")
                .first()
            )
            return redirect(
                reverse("ingest:match_check", args=[nxt.pk])
                if nxt
                else reverse("ingest:scannedcheck_list")
            )

        messages.error(request, "Please fix the errors below.")

    # 4) POST: create new transaction
    if request.method == "POST" and "create_new" in request.POST:
        form = CreateNewTransactionForm(request.POST)
        if form.is_valid():
            sub = None
            if form.cleaned_data.get("subcategory_id"):
                sub = Category.objects.filter(
                    pk=form.cleaned_data["subcategory_id"]
                ).first()
            txn = Transaction.objects.create(
                date=form.cleaned_data["date"],
                amount=form.cleaned_data["amount"],
                description=form.cleaned_data["description"],
                bank_account=form.cleaned_data["bank_account"],
                payoree=form.cleaned_data["payoree"] or None,
                subcategory=sub,
                account_type="Check",
            )
            sc.linked_transaction = txn
            sc.status = "confirmed"
            sc.save(update_fields=["linked_transaction", "status"])
            messages.success(request, f"Created T-{txn.pk} and linked check.")
            nxt = (
                ScannedCheck.objects.filter(status="unmatched")
                .exclude(pk=sc.pk)
                .order_by("id")
                .first()
            )
            return redirect(
                reverse("ingest:match_check", args=[nxt.pk])
                if nxt
                else reverse("ingest:scannedcheck_list")
            )

        messages.error(request, "Please correct the new transaction form.")

    # Default render (prefill preview with top candidate if any)
    desc_preview = ""
    if top_txn:
        desc_preview = render_description(
            csv_desc=top_txn.description or "",
            check_no=sc.check_number or None,
            payoree=getattr(sc.payoree, "name", None),
            memo=sc.memo_text or None,
        )

    context = {
        "sc": sc,
        "bank_form": bank_form,
        "candidates": cands,
        "selected": cands[0].txn if cands else None,
        "why": why,
        "desc_preview": desc_preview,
        "payoree_qs": Payoree.objects.order_by("name")[
            :500
        ],  # or whatever limit/filter you prefer
    }

    return render(
        request,
        "ingest/match_check.html",
        {
            "sc": sc,
            "bank_form": bank_form,
            "candidates": cands,
            "selected": top_txn,
            "desc_preview": desc_preview,
            "why": why,
        },
    )
