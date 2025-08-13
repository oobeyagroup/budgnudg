# ingest/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class MappingProfile(models.Model):
    name = models.CharField(max_length=100, unique=True)
    column_map = models.JSONField()  
    options = models.JSONField(default=dict, blank=True)  # date formats, sign rules, etc.
    description = models.TextField(blank=True, default="") # optional notes about this profile, ex what account it maps

    def __str__(self):
        return self.description


class ImportBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    # make optional so batch creation never fails due to missing name
    source_filename = models.CharField(max_length=255, blank=True, default="")

    header = models.JSONField(default=list)  # ordered list of column names
    row_count = models.IntegerField(default=0)
    profile = models.ForeignKey(MappingProfile, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=20, default="uploaded")  # uploaded|previewed|committed|failed
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["profile"]),
        ]

    def __str__(self):
        return f"Batch {self.pk} — {self.source_filename or 'unnamed'}"


class ImportRow(models.Model):
    """
    One CSV line captured during ingest.
    raw:      original CSV row (dict) as parsed by DictReader
    parsed:   result of map_row_with_profile (includes _date/_amount/_suggestions/_errors)
    norm_*:   denormalized typed columns for fast filtering/sorting
    """
    batch = models.ForeignKey("ingest.ImportBatch", on_delete=models.CASCADE, related_name="rows")
    row_index = models.PositiveIntegerField()

    raw = models.JSONField(default=dict)          # {"Posting Date": "...", "Amount": "...", ...}
    parsed = models.JSONField(default=dict, blank=True)

    norm_date = models.DateField(null=True, blank=True)
    norm_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    norm_description = models.TextField(blank=True, default="")

    suggestions = models.JSONField(default=dict, blank=True)  # e.g. {"subcategory":"Fast Food","payoree":"STARBUCKS"}
    errors = models.JSONField(default=list, blank=True)       # e.g. ["date: ...", "amount: ..."]

    is_duplicate = models.BooleanField(default=False)

    # Keep as int for now; add an index for reverse lookups.
    committed_txn_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["row_index"]
        constraints = [
            models.UniqueConstraint(fields=["batch", "row_index"], name="uniq_batch_rowidx"),
        ]
        indexes = [
            models.Index(fields=["batch", "row_index"]),
            models.Index(fields=["is_duplicate"]),
            models.Index(fields=["norm_date"]),
            models.Index(fields=["batch", "committed_txn_id"]),
        ]

    def __str__(self):
        return f"ImportRow(batch={self.batch_id}, idx={self.row_index})"