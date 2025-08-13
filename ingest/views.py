
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from transactions.utils import trace
from ingest.models import ImportBatch, MappingProfile
from ingest.forms import UploadCSVForm, AssignProfileForm, CommitForm
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch

import logging


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
        if batch and batch.profile:
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
        else:
            messages.warning(self.request, "Please select a profile before previewing transactions.")
            return redirect("ingest:batch_preview", pk=batch.pk if batch else 1)
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
    profiles = MappingProfile.objects.all()
    if request.method == "POST":
        form = CommitForm(request.POST)
        if form.is_valid():
            imported, dups, skipped = commit_batch(batch, form.cleaned_data["bank_account"])
            messages.success(request, f"Imported {len(imported)}; skipped {len(skipped)}.")
            return redirect("transactions_list")
    else:
        form = CommitForm()
    return render(request, "ingest/commit_form.html", {
        "form": form,
        "batch": batch,
        "profiles": profiles,
        "selected_profile_id": batch.profile_id
    })

class BatchListView(ListView):
    model = ImportBatch
    template_name = "ingest/batch_list.html"
    context_object_name = "batches"
    paginate_by = 20