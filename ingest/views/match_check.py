from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from transactions.utils import trace
from transactions.models import Transaction
from ingest.models import ScannedCheck
from ingest.forms import (
    CheckReviewForm,
    BankPickForm,
    AttachEditForm,
    CreateNewTransactionForm,
)
from ..services.matching import find_candidates, render_description

import logging

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
@trace
def match_check(request, pk: int):
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
        .values_list("bank_account__name", flat=True)
        .distinct()
        .order_by("bank_account__name")
    )

    # Handle transaction search
    search_triggered = False
    if request.method == "POST" and "look_for_transactions" in request.POST:
        search_triggered = True

        # Save form data if valid
        if form.is_valid():
            form.save()
            messages.success(request, "Check details saved.")

            # Handle bank selection from the form
            bank_form = BankPickForm(request.POST, accounts=_existing_bank_accounts())
            if bank_form.is_valid():
                bank_value = bank_form.cleaned_data["bank_account"]
                if bank_value:
                    ScannedCheck.objects.filter(pk=sc.pk).update(
                        bank_account=bank_value
                    )
                    sc.refresh_from_db()  # Refresh the instance to get the updated bank_account
        else:
            messages.error(request, "Please fix the errors below.")
            search_triggered = False  # Don't perform search if form is invalid

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

    prev_url = reverse("ingest:match_check", args=[prev_id]) if prev_id else None
    next_url = reverse("ingest:match_check", args=[next_id]) if next_id else None
    cancel_url = reverse("ingest:scannedcheck_list")  # make sure this URL name exists

    if (
        request.method == "POST"
        and not search_triggered
        and "attach_save" not in request.POST
        and "create_new" not in request.POST
    ):
        if form.is_valid():
            form.save()  # <-- persist changes to ScannedCheck

            # Also handle bank selection for regular save
            bank_form = BankPickForm(request.POST, accounts=_existing_bank_accounts())
            if bank_form.is_valid():
                bank_value = bank_form.cleaned_data["bank_account"]
                if bank_value:
                    ScannedCheck.objects.filter(pk=sc.pk).update(
                        bank_account=bank_value
                    )
                    sc.refresh_from_db()  # Refresh the instance to get the updated bank_account

            messages.success(request, "Check saved.")

            # Navigate if user clicked a nav button
            if "next" in request.POST and next_url:
                return redirect(next_url)
            if "prev" in request.POST and prev_url:
                return redirect(prev_url)
            if "cancel" in request.POST:
                return redirect(cancel_url)

            # Default after save: stay on the page
            return redirect(reverse("ingest:match_check", args=[sc.pk]))
        else:
            messages.error(request, "Please fix the errors below.")

    # For payoree assignment partial
    payorees = form.fields["payoree"].queryset if "payoree" in form.fields else []
    payoree_matches = []  # You can add logic for suggestions if desired

    # 1) Check if search should be performed
    bank = sc.bank_account or ""
    # Initialize bank form for rendering - don't use POST data if it's not a look_for_transactions request
    bank_form_data = None
    if request.method == "POST" and "look_for_transactions" in request.POST:
        bank_form_data = request.POST
    bank_form = BankPickForm(
        bank_form_data,
        accounts=_existing_bank_accounts(),
        initial={"bank_account": bank or ""},
    )
    perform_search = search_triggered and bank

    # Always perform search if attach_save is requested (to get current candidates)
    perform_attach = request.method == "POST" and "attach_save" in request.POST
    if perform_attach:
        perform_search = True

    if not perform_search:
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

    # 2) Candidate list (scored) - only when search is triggered or attach is requested
    cands = find_candidates(
        bank=bank,
        check_no=sc.check_number or "",
        amount=sc.amount,
    )
    top = cands[0] if cands else None
    top_txn = top.txn if top else None
    why = top.why if top else []

    # 3) POST: attach to existing
    if perform_attach:
        form = AttachEditForm(request.POST)
        logger.debug(f"DEBUG: Attach form data: {request.POST}")
        logger.debug(f"DEBUG: Form is valid: {form.is_valid()}")
        logger.debug(f"DEBUG: top_txn exists: {top_txn is not None}")
        if form.is_valid():
            logger.debug(f"DEBUG: Form cleaned data: {form.cleaned_data}")
        if form.is_valid() and top_txn:  # Ensure we have a selected transaction
            logger.debug(f"DEBUG: Expected transaction ID: {top_txn.pk}")
            logger.debug(f"DEBUG: Form transaction ID: {form.cleaned_data['transaction_id']}")
            txn = get_object_or_404(Transaction, pk=form.cleaned_data["transaction_id"])
            logger.debug(f"DEBUG: Found transaction: {txn.pk}")

            # Check if transaction already has a linked scanned check
            try:
                existing_scanned_check = txn.scanned_check
                if existing_scanned_check and existing_scanned_check != sc:
                    logger.debug(
                        f"DEBUG: Transaction {txn.pk} already linked to ScannedCheck {existing_scanned_check.pk}"
                    )
                    messages.error(
                        request,
                        f"Transaction {txn.pk} is already linked to another check.",
                    )
                    return redirect(reverse("ingest:match_check", args=[sc.pk]))
            except:
                # No existing scanned_check, which is fine
                pass

            # Check if our ScannedCheck already has a linked transaction
            if sc.linked_transaction and sc.linked_transaction != txn:
                logger.debug(
                    f"DEBUG: ScannedCheck {sc.pk} already linked to Transaction {sc.linked_transaction.pk}"
                )
                # Clear the existing link first
                logger.debug(f"DEBUG: Clearing existing link from ScannedCheck {sc.pk}")
                sc.linked_transaction = None
                sc.save()

            # Verify the transaction matches what we expect
            if txn.pk != top_txn.pk:
                logger.debug(
                    f"DEBUG: Transaction ID mismatch! Expected {top_txn.pk}, got {txn.pk}"
                )
                messages.error(request, "Transaction ID mismatch.")
                return redirect(reverse("ingest:match_check", args=[sc.pk]))
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
            logger.debug(f"DEBUG: Transaction saved")

            # Link + status
            sc.refresh_from_db()  # Refresh the instance to avoid stale data issues
            sc.linked_transaction = txn
            sc.status = "confirmed"
            try:
                sc.save()  # Try saving without update_fields
                logger.debug(
                    f"DEBUG: ScannedCheck saved successfully. linked_transaction = {sc.linked_transaction}"
                )
            except Exception as e:
                logger.debug(f"DEBUG: Error saving ScannedCheck: {e}")
                messages.error(request, f"Error saving ScannedCheck: {e}")
                return redirect(reverse("ingest:match_check", args=[sc.pk]))

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
            #     reverse("ingest:match_check", args=[nxt.pk])
            #     if nxt
            #     else reverse("ingest:scannedcheck_list")
            reverse("ingest:scannedcheck_list")
            )

        else:
            if not top_txn:
                messages.error(request, "No transaction selected to attach to.")
            else:
                messages.error(request, f"Attach form errors: {form.errors}")
            # Don't redirect, stay on page to show errors

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

def _existing_bank_accounts() -> list[str]:
    from transactions.models import Transaction

    return list(
        Transaction.objects.exclude(bank_account__isnull=True)
        .values_list("bank_account__name", flat=True)
        .distinct()
    )

