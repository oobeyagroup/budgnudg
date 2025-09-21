from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal


class Budget(models.Model):
    """Monthly budget allocation for categories, subcategories, payorees, or needs levels."""

    # Scope - following existing precedence: category > subcategory > payoree
    category = models.ForeignKey(
        "transactions.Category",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to={"parent__isnull": True},  # Top-level categories only
        help_text="Budget applies to this category",
    )
    subcategory = models.ForeignKey(
        "transactions.Category",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subcategory_budgets",
        limit_choices_to={"parent__isnull": False},  # Subcategories only
        help_text="Budget applies to this subcategory",
    )
    payoree = models.ForeignKey(
        "transactions.Payoree",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Budget applies to this payoree",
    )

    # Needs level integration with existing Transaction model system
    needs_level = models.CharField(
        max_length=20,
        choices=[
            ("critical", "Critical"),
            ("core", "Core"),
            ("lifestyle", "Lifestyle"),
            ("discretionary", "Discretionary"),
            ("luxury", "Luxury"),
            ("deferred", "Deferred"),
        ],
        null=True,
        blank=True,
        help_text="Budget applies to this needs level",
    )

    # Time period - monthly granularity as specified
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )

    # Budget amount
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Monthly budget amount",
    )

    # AI/ML suggestion tracking
    is_ai_suggested = models.BooleanField(
        default=False, help_text="True if this budget was auto-populated by AI"
    )
    baseline_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Historical baseline used for AI suggestion",
    )

    # User notes and metadata
    user_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Integration with recurring transactions
    recurring_series = models.ForeignKey(
        "transactions.RecurringSeries",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Connected recurring transaction series",
    )

    class Meta:
        # Ensure one budget per scope per month
        unique_together = [
            ("year", "month", "category", "subcategory", "payoree", "needs_level")
        ]
        ordering = ["-year", "-month", "category__name"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["category"]),
            models.Index(fields=["needs_level"]),
            models.Index(fields=["recurring_series"]),
        ]

    def clean(self):
        """Validate that subcategory belongs to category if both are specified."""
        if self.subcategory and self.category:
            if self.subcategory.parent != self.category:
                raise ValidationError(
                    {
                        "subcategory": f'Subcategory "{self.subcategory}" must belong to category "{self.category}"'
                    }
                )

        # At least one scope field must be specified
        if not any([self.category, self.subcategory, self.payoree, self.needs_level]):
            raise ValidationError(
                "At least one scope field (category, subcategory, payoree, or needs_level) must be specified"
            )

    def __str__(self):
        scope_parts = []
        if self.category:
            scope_parts.append(self.category.name)
        if self.subcategory:
            scope_parts.append(f"→ {self.subcategory.name}")
        if self.payoree:
            scope_parts.append(f"({self.payoree.name})")
        if self.needs_level:
            scope_parts.append(f"[{self.needs_level.title()}]")

        scope = " ".join(scope_parts) if scope_parts else "General"
        return f"{scope} - {self.month:02d}/{self.year}: ${self.amount}"

    @property
    def period_display(self):
        """Human-readable period display."""
        from calendar import month_name

        return f"{month_name[self.month]} {self.year}"

    def get_variance_vs_baseline(self):
        """Calculate variance from baseline amount."""
        if not self.baseline_amount:
            return None
        return self.amount - self.baseline_amount

    def get_variance_percentage(self):
        """Calculate percentage variance from baseline."""
        if not self.baseline_amount or self.baseline_amount == 0:
            return None
        return ((self.amount - self.baseline_amount) / self.baseline_amount) * 100

    @property
    def scope_key(self):
        """Generate a unique key for this budget's scope."""
        return (
            self.category_id or 0,
            self.subcategory_id or 0,
            self.payoree_id or 0,
            self.needs_level or "",
        )


class BudgetPeriod(models.Model):
    """Represents a complete budget period (e.g., 2024-03) with aggregate info."""

    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )

    # Aggregate totals for quick reference
    total_budgeted = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    baseline_total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )

    # Status tracking
    is_finalized = models.BooleanField(
        default=False, help_text="True when user has finalized this budget period"
    )

    notes = models.TextField(blank=True, help_text="Period-level notes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("year", "month")]
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["is_finalized"]),
        ]

    def __str__(self):
        from calendar import month_name

        status = " (Finalized)" if self.is_finalized else ""
        return f"Budget Period: {month_name[self.month]} {self.year}{status}"

    @property
    def period_display(self):
        """Human-readable period display."""
        from calendar import month_name

        return f"{month_name[self.month]} {self.year}"

    def get_variance_vs_baseline(self):
        """Calculate total variance from baseline."""
        return self.total_budgeted - self.baseline_total

    def get_budget_count(self):
        """Get number of budget items in this period."""
        return Budget.objects.filter(year=self.year, month=self.month).count()

    def update_totals(self):
        """Recalculate aggregate totals from Budget items."""
        budgets = Budget.objects.filter(year=self.year, month=self.month)

        self.total_budgeted = sum(b.amount for b in budgets)
        self.baseline_total = sum(b.baseline_amount or Decimal("0.00") for b in budgets)
        self.save(update_fields=["total_budgeted", "baseline_total", "updated_at"])
