
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from django.utils.decorators import method_decorator
from transactions.utils import trace
from ingest.models import ImportBatch, MappingProfile
from ingest.forms import UploadCSVForm, AssignProfileForm
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch

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
        return redirect("transactions_list")
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