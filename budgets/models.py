from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import datetime, date
from calendar import monthrange


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

    @property
    def start_date(self):
        """Get the start date of the budget plan period."""
        return date(self.year, self.month, 1)

    @property
    def end_date(self):
        """Get the end date of the budget plan period."""
        import calendar

        last_day = calendar.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, last_day)

    @property
    def period_display(self):
        """Human-readable period display."""
        from calendar import month_name

        return f"{month_name[self.month]} {self.year}"


class BudgetAllocation(models.Model):
    """
    Simplified payoree-centric budget allocation.

    Each allocation is tied to a specific payoree, making budgeting more concrete
    and actionable. Categories are derived from the payoree's default category.
    """

    # Link to budget plan
    budget_plan = models.ForeignKey(
        BudgetPlan,
        on_delete=models.CASCADE,
        related_name="allocations",
        help_text="Budget plan this allocation belongs to",
    )

    # Simplified: Only payoree-based allocations
    payoree = models.ForeignKey(
        "transactions.Payoree",
        on_delete=models.CASCADE,
        help_text="Payoree for this budget allocation",
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
        # Simplified: One allocation per payoree per budget plan
        unique_together = [("budget_plan", "payoree")]
        ordering = ["budget_plan", "payoree__name"]
        indexes = [
            models.Index(fields=["budget_plan"]),
            models.Index(fields=["payoree"]),
        ]

    def __str__(self):
        return f"{self.budget_plan.name}: {self.payoree.name} - ${self.amount}"

    def clean(self):
        """Simplified validation - only need to ensure payoree is provided."""
        if not self.payoree_id:
            raise ValidationError("Payoree is required for budget allocations")

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

    @property
    def effective_category(self):
        """Get effective category from payoree's default category."""
        return self.payoree.default_category

    @property
    def effective_subcategory(self):
        """Get effective subcategory from payoree's default subcategory."""
        return self.payoree.default_subcategory

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
        """Get current amount spent for this payoree in this period."""
        from transactions.models import Transaction

        # Get transactions for this payoree in this budget period
        start_date = date(self.year, self.month, 1)
        if self.month == 12:
            end_date = date(self.year + 1, 1, 1)
        else:
            end_date = date(self.year, self.month + 1, 1)

        transactions = Transaction.objects.filter(
            payoree=self.payoree, date__gte=start_date, date__lt=end_date
        )

        return sum(abs(t.amount) for t in transactions)

    def get_spent_percentage(self):
        """Get percentage of allocation spent."""
        if self.amount == 0:
            return 0
        spent = self.get_current_spent()
        return (spent / abs(self.amount)) * 100

    def get_remaining_amount(self):
        """Get remaining allocation amount."""
        return abs(self.amount) - self.get_current_spent()

    @property
    def start_date(self):
        """Budget period start date."""
        return date(self.year, self.month, 1)

    @property
    def end_date(self):
        """Budget period end date."""
        import calendar

        last_day = calendar.monthrange(self.year, self.month)[1]
        return date(self.year, self.month, last_day)

    @property
    def is_active(self):
        """Check if allocation is for current or future period."""
        return self.budget_plan.is_active


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


def get_or_create_misc_payoree(
    name_suffix, default_category=None, default_subcategory=None
):
    """
    Create or get a 'misc' payoree for category/subcategory-level budgeting.

    Args:
        name_suffix: e.g., "Groceries - Misc" or "Utilities - Misc"
        default_category: Category to assign to this misc payoree
        default_subcategory: Optional subcategory

    Returns:
        Payoree instance for misc allocations
    """
    from transactions.models import Payoree

    payoree, created = Payoree.objects.get_or_create(
        name=name_suffix,
        defaults={
            "default_category": default_category,
            "default_subcategory": default_subcategory,
        },
    )

    if created:
        print(f"Created misc payoree: {name_suffix}")

    return payoree


# Compatibility alias for existing code during migration
Budget = BudgetAllocation
