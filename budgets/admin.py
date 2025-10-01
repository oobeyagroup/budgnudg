from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from .models import BudgetPlan, BudgetAllocation, BudgetPeriod


@admin.register(BudgetPlan)
class BudgetPlanAdmin(admin.ModelAdmin):
    """Admin interface for BudgetPlan model."""

    list_display = [
        "name",
        "period_display",
        "is_active",
        "allocation_count",
        "total_amount",
        "created_at",
    ]
    list_filter = ["year", "month", "is_active"]
    search_fields = ["name"]
    ordering = ["-year", "-month", "name"]
    readonly_fields = ["created_at", "updated_at"]

    def period_display(self, obj):
        """Display period in readable format."""
        return obj.period_display

    period_display.short_description = "Period"

    def allocation_count(self, obj):
        """Display count of allocations in this plan."""
        return obj.budgetallocation_set.count()

    allocation_count.short_description = "Allocations"

    def total_amount(self, obj):
        """Display total allocated amount."""
        total = obj.budgetallocation_set.aggregate(total=Sum("amount"))["total"] or 0
        return f"${total:,.2f}"

    total_amount.short_description = "Total Allocated"


@admin.register(BudgetAllocation)
class BudgetAllocationAdmin(admin.ModelAdmin):
    """Simplified admin interface for payoree-centric BudgetAllocation model."""

    list_display = [
        "budget_plan",
        "payoree",
        "effective_category_display",
        "amount",
        "baseline_amount",
        "variance_display",
        "is_ai_suggested",
        "recurring_series",
    ]

    list_filter = [
        "budget_plan__year",
        "budget_plan__month",
        "is_ai_suggested",
        "payoree__default_category",
        ("recurring_series", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "budget_plan__name",
        "payoree__name",
        "payoree__default_category__name",
        "user_note",
    ]

    ordering = [
        "-budget_plan__year",
        "-budget_plan__month",
        "budget_plan__name",
        "payoree__name",
    ]

    readonly_fields = ["created_at", "updated_at", "effective_category_display"]

    fieldsets = (
        (
            "Budget Plan",
            {"fields": ("budget_plan",)},
        ),
        (
            "Allocation",
            {"fields": ("payoree", "effective_category_display")},
        ),
        ("Amount Details", {"fields": ("amount", "baseline_amount")}),
        ("AI & Integration", {"fields": ("is_ai_suggested", "recurring_series")}),
        (
            "Notes & Metadata",
            {
                "fields": ("user_note", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def effective_category_display(self, obj):
        """Display the effective category from the payoree."""
        if obj.payoree and obj.payoree.default_category:
            category_display = f"📁 {obj.payoree.default_category.name}"
            if obj.payoree.default_subcategory:
                category_display += f" → {obj.payoree.default_subcategory.name}"
            return category_display
        return "No category set"

    effective_category_display.short_description = "Category"

    def variance_display(self, obj):
        """Display variance with color coding."""
        variance = obj.get_variance_vs_baseline()
        if variance is None:
            return "—"

        if variance > 0:
            color = "green"
            sign = "+"
        else:
            color = "red"
            sign = ""

        # Format the variance as a string first to avoid SafeString issues
        variance_str = f"{variance:.2f}"
        return format_html(
            '<span style="color: {};">{}{}</span>', color, sign, variance_str
        )

    variance_display.short_description = "Variance"

    actions = ["mark_ai_suggested", "mark_user_created", "duplicate_to_next_month"]

    def mark_ai_suggested(self, request, queryset):
        """Mark selected budgets as AI suggested."""
        updated = queryset.update(is_ai_suggested=True)
        self.message_user(
            request, f"Successfully marked {updated} budget(s) as AI suggested."
        )

    mark_ai_suggested.short_description = "Mark as AI suggested"

    def mark_user_created(self, request, queryset):
        """Mark selected budgets as user created."""
        updated = queryset.update(is_ai_suggested=False)
        self.message_user(
            request, f"Successfully marked {updated} budget(s) as user created."
        )

    mark_user_created.short_description = "Mark as user created"


@admin.register(BudgetPeriod)
class BudgetPeriodAdmin(admin.ModelAdmin):
    """Admin interface for BudgetPeriod model."""

    list_display = [
        "period_display",
        "budget_count_display",
        "total_budgeted",
        "baseline_total",
        "variance_display",
        "is_finalized",
        "updated_at",
    ]

    list_filter = [
        "year",
        "is_finalized",
    ]

    ordering = ["-year", "-month"]

    readonly_fields = ["created_at", "updated_at", "budget_count_display"]

    fieldsets = (
        ("Period Info", {"fields": ("year", "month", "is_finalized")}),
        (
            "Totals",
            {"fields": ("total_budgeted", "baseline_total", "budget_count_display")},
        ),
        ("Notes & Metadata", {"fields": ("notes", "created_at", "updated_at")}),
    )

    def budget_count_display(self, obj):
        """Display number of budget items in this period."""
        return obj.get_budget_count()

    budget_count_display.short_description = "Budget Items"

    def variance_display(self, obj):
        """Display variance with color coding."""
        variance = obj.get_variance_vs_baseline()
        if variance is None:
            return "—"

        if variance > 0:
            color = "green"
            sign = "+"
        else:
            color = "red"
            sign = ""

        # Format the variance as a string first to avoid SafeString issues
        variance_str = f"{variance:.2f}"
        return format_html(
            '<span style="color: {};">{}{}</span>', color, sign, variance_str
        )

    variance_display.short_description = "Variance vs Baseline"

    actions = ["recalculate_totals", "finalize_periods", "unfinalize_periods"]

    def recalculate_totals(self, request, queryset):
        """Recalculate totals for selected periods."""
        for period in queryset:
            period.update_totals()

        self.message_user(
            request,
            f"Successfully recalculated totals for {queryset.count()} period(s).",
        )

    recalculate_totals.short_description = "Recalculate totals"

    def finalize_periods(self, request, queryset):
        """Finalize selected budget periods."""
        updated = queryset.update(is_finalized=True)
        self.message_user(
            request, f"Successfully finalized {updated} budget period(s)."
        )

    finalize_periods.short_description = "Finalize periods"

    def unfinalize_periods(self, request, queryset):
        """Unfinalize selected budget periods."""
        updated = queryset.update(is_finalized=False)
        self.message_user(
            request, f"Successfully unfinalized {updated} budget period(s)."
        )

    unfinalize_periods.short_description = "Unfinalize periods"
