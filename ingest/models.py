# ingest/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from transactions.models import Transaction

User = get_user_model()


class FinancialAccount(models.Model):
    name = models.CharField(max_length=100, unique=True)
    column_map = models.JSONField()
    options = models.JSONField(
        default=dict, blank=True
    )  # date formats, sign rules, etc.
    description = models.TextField(
        blank=True, default=""
    )  # optional notes about this profile, ex what account it maps

    def __str__(self):
        return self.description


class ImportBatch(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL
    )
    # make optional so batch creation never fails due to missing name
    source_filename = models.CharField(max_length=255, blank=True, default="")
    header = models.JSONField(default=list)  # ordered list of column names
    row_count = models.IntegerField(default=0)
    profile = models.ForeignKey(
        FinancialAccount, null=True, blank=True, on_delete=models.SET_NULL
    )
    status = models.CharField(max_length=20, default="uploaded")
    # uploaded|previewed|committed|failed
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["profile"]),
        ]

    def __str__(self):
        # Use an em dash for nicer formatting (tests expect this in some places)
        return f"Batch {self.pk} — {self.source_filename or 'unnamed'}"


class ImportRow(models.Model):
    """
    One CSV line captured during ingest.
    raw: oiginal CS row (dict) as parsed by DictReader
    parsed: result of map_row_with_profile (includes date/_amount/suggestions/errors)
    norm_*:denormalized typed columns for fast filtering/sorting
    """

    batch = models.ForeignKey(
        "ingest.ImportBatch", on_delete=models.CASCADE, related_name="rows"
    )
    row_index = models.PositiveIntegerField()
    raw = models.JSONField(default=dict)
    parsed = models.JSONField(default=dict, blank=True)
    # {"Posting Date": "...", "Amount": "...", ...}
    norm_date = models.DateField(null=True, blank=True)
    norm_amount = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    norm_description = models.TextField(blank=True, default="")

    suggestions = models.JSONField(
        default=dict, blank=True
    )  # e.g. {"subcategory": "Fast Food", "payoree": "STARBUCKS"}
    errors = models.JSONField(default=list, blank=True)
    # e.g. ["date: ...", "amount: ..."]

    is_duplicate = models.BooleanField(default=False)

    # Keep as int for now; add an index for reverse lookups.
    committed_txn_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["row_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "row_index"], name="uniq_batch_rowid"
            ),
        ]
        indexes = [
            models.Index(fields=["batch", "row_index"]),
            models.Index(fields=["is_duplicate"]),
            models.Index(fields=["norm_date"]),
            models.Index(fields=["batch", "committed_txn_id"]),
        ]

    def __str__(self):
        return f"ImportRow(batch={self.batch_id}, idx={self.row_index})"


class ScannedCheck(models.Model):
    image_file = models.ImageField(upload_to="checks/", blank=True, null=True)
    original_filename = models.CharField(
        max_length=255, db_index=True, blank=True, null=True
    )
    content_md5 = models.CharField(
        max_length=32, db_index=True, blank=True
    )  # set on save
    bank_account = models.CharField(max_length=50, blank=True)
    check_number = models.CharField(max_length=20, blank=True)
    date = models.DateField(null=True, blank=True)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    payoree = models.ForeignKey(
        "transactions.Payoree", null=True, blank=True, on_delete=models.SET_NULL
    )
    memo_text = models.CharField(max_length=255, blank=True)
    # link to a Transaction if matched/resolved

    linked_transaction = models.OneToOneField(
        Transaction,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scanned_check",
    )
    status = models.CharField(
        max_length=16,
        choices=[
            ("unmatched", "Unmatched"),
            ("matched", "Matched"),
            ("confirmed", "Confirmed"),
        ],
        default="unmatched",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # avoid dup imports; filename can collide across batches, so md5 is stronger
            models.UniqueConstraint(
                fields=["content_md5"], name="unique_scannedcheck_md5"
            )
        ]

    def __str__(self):
        return f"Check {self.pk} - {self.original_filename}"
