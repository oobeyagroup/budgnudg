from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime


# Temporary alias for compatibility during migration
Budget = None  # Will be set after BudgetAllocation is defined


class BudgetPlan(models.Model):
    """Overall budget plan (lean, normal, splurge) for a specific time period."""

    name = models.CharField(
        max_length=50, help_text="Budget plan name (e.g., 'Lean', 'Normal', 'Splurge')"
    )
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    is_active = models.BooleanField(
        default=False, help_text="Whether this plan is currently active"
    )
    description = models.TextField(
        blank=True, help_text="Optional description of this budget plan"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("name", "year", "month")]
        ordering = ["-year", "-month", "name"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.year}-{self.month:02d}"


class BudgetAllocation(models.Model):
    """Individual spending allocation within a budget plan for categories, subcategories, payorees, or needs levels."""

    # Link to budget plan
    budget_plan = models.ForeignKey(
        BudgetPlan,
        on_delete=models.CASCADE,
        related_name="allocations",
        help_text="Budget plan this allocation belongs to",
    )

    # Scope - following existing precedence: category > subcategory > payoree
    category = models.ForeignKey(
        "transactions.Category",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        limit_choices_to={"parent__isnull": True},  # Top-level categories only
        help_text="Allocation applies to this category",
    )
    subcategory = models.ForeignKey(
        "transactions.Category",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subcategory_allocations",
        limit_choices_to={"parent__isnull": False},  # Subcategories only
        help_text="Allocation applies to this subcategory",
    )
    payoree = models.ForeignKey(
        "transactions.Payoree",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text="Allocation applies to this payoree",
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
        help_text="Allocation applies to this needs level",
    )

    # Budget allocation amount
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Allocation amount (positive for income, negative for expenses)",
    )

    # AI/ML suggestion tracking
    is_ai_suggested = models.BooleanField(
        default=False, help_text="True if this allocation was auto-populated by AI"
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
        # Ensure one allocation per scope per budget plan
        unique_together = [
            ("budget_plan", "category", "subcategory", "payoree", "needs_level")
        ]
        ordering = ["budget_plan", "category__name"]
        indexes = [
            models.Index(fields=["budget_plan"]),
            models.Index(fields=["category"]),
            models.Index(fields=["subcategory"]),
            models.Index(fields=["payoree"]),
        ]

    def __str__(self):
        scope_parts = []
        if self.category:
            scope_parts.append(self.category.name)
        if self.subcategory:
            scope_parts.append(f"→ {self.subcategory.name}")
        if self.payoree:
            scope_parts.append(f"({self.payoree.name})")
        if self.needs_level:
            scope_parts.append(f"[{self.get_needs_level_display()}]")

        scope = " ".join(scope_parts) if scope_parts else "General Allocation"
        return f"{self.budget_plan.name}: {scope} - ${self.amount}"

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

    @property
    def year(self):
        """Get year from budget plan."""
        return self.budget_plan.year

    @property
    def month(self):
        """Get month from budget plan."""
        return self.budget_plan.month

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

    def get_current_spent(self):
        """Get current amount spent for this allocation (placeholder for future integration)."""
        # TODO: Integrate with transaction system to calculate actual spending
        return Decimal("0.00")

    def get_spent_percentage(self):
        """Get percentage of allocation spent."""
        if self.amount == 0:
            return 0
        spent = self.get_current_spent()
        return (spent / abs(self.amount)) * 100

    def get_remaining_amount(self):
        """Get remaining allocation amount."""
        return self.amount - self.get_current_spent()

    @property
    def start_date(self):
        """Budget period start date."""
        from datetime import datetime

        return datetime(self.year, self.month, 1).date()

    @property
    def end_date(self):
        """Budget period end date."""
        from datetime import datetime, date
        import calendar

        last_day = calendar.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, last_day)

    @property
    def is_active(self):
        """Check if allocation is for current or future period."""
        return self.budget_plan.is_active

    @property
    def scope_key(self):
        """Generate a unique key for this allocation's scope."""
        return (
            self.category_id or 0,
            self.subcategory_id or 0,
            self.payoree_id or 0,
            self.needs_level or "",
        )


# Legacy model - keeping for backwards compatibility, but may be deprecated
class BudgetPeriod(models.Model):
    """Legacy: Represents a complete budget period (e.g., 2024-03) with aggregate info."""

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

    def get_allocation_count(self):
        """Get number of budget allocations in this period."""
        return BudgetAllocation.objects.filter(
            budget_plan__year=self.year, budget_plan__month=self.month
        ).count()

    def update_totals(self):
        """Recalculate aggregate totals from BudgetAllocation items."""
        allocations = BudgetAllocation.objects.filter(
            budget_plan__year=self.year, budget_plan__month=self.month
        )

        self.total_budgeted = sum(a.amount for a in allocations)
        self.baseline_total = sum(
            a.baseline_amount or Decimal("0.00") for a in allocations
        )
        self.save(update_fields=["total_budgeted", "baseline_total", "updated_at"])


# Compatibility alias for existing code during migration
Budget = BudgetAllocation
