from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib import messages
from django.urls import reverse
from ingest.models import ImportBatch, MappingProfile
from ingest.forms import UploadCSVForm, AssignProfileForm, CommitForm
from ingest.services.staging import create_batch_from_csv
from ingest.services.mapping import preview_batch, commit_batch, apply_profile_to_batch

class BatchListView(ListView):
    model = ImportBatch
    template_name = "ingest/batch_list.html"
    context_object_name = "batches"
    ordering = ["-created_at"]

class BatchDetailView(DetailView):
    model = ImportBatch
    template_name = "ingest/batch_detail.html"
    context_object_name = "batch"

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
            return redirect("ingest:batch_detail", pk=batch.pk)
    else:
        form = UploadCSVForm()
    return render(request, "ingest/upload_form.html", {"form": form})

def apply_profile(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    profile = get_object_or_404(MappingProfile, pk=request.POST.get("profile_id"))
    # optionally pass the bank account if you let the user choose it early:
    updated, dup_count = apply_profile_to_batch(batch, profile, bank_account_hint=request.POST.get("bank_account"))
    messages.success(request, f"Mapped {updated} rows. Duplicates flagged: {dup_count}.")
    return redirect("ingest:batch_detail", pk=batch.id)

# def apply_profile(request, pk):
#     batch = get_object_or_404(ImportBatch, pk=pk)
#     if request.method == "POST":
#         form = AssignProfileForm(request.POST)
#         if form.is_valid():
#             batch.profile = form.cleaned_data["profile"]
#             batch.save(update_fields=["profile"])
#             preview_batch(batch)
#             messages.success(request, "Profile applied. Preview updated.")
#             return redirect("ingest:batch_detail", pk=batch.pk)
#     else:
#         form = AssignProfileForm(initial={"profile": batch.profile_id})
#     return render(request, "ingest/assign_profile.html", {"form": form, "batch": batch})

def commit(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    if request.method == "POST":
        form = CommitForm(request.POST)
        if form.is_valid():
            imported, dups, skipped = commit_batch(batch, form.cleaned_data["bank_account"])
            messages.success(request, f"Imported {len(imported)}; skipped {len(skipped)}.")
            return redirect("transactions_list")
    else:
        form = CommitForm()
    return render(request, "ingest/commit_form.html", {"form": form, "batch": batch})