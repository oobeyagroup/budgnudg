from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html
from .models import Budget, BudgetPeriod


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    """Admin interface for Budget model."""

    list_display = [
        "period_display",
        "scope_display",
        "amount",
        "baseline_amount",
        "variance_display",
        "needs_level",
        "is_ai_suggested",
        "recurring_series",
    ]

    list_filter = [
        "year",
        "month",
        "needs_level",
        "is_ai_suggested",
        "category",
        ("recurring_series", admin.RelatedOnlyFieldListFilter),
    ]

    search_fields = [
        "category__name",
        "subcategory__name",
        "payoree__name",
        "user_note",
    ]

    ordering = ["-year", "-month", "category__name"]

    readonly_fields = ["created_at", "updated_at"]

    fieldsets = (
        (
            "Budget Scope",
            {"fields": ("category", "subcategory", "payoree", "needs_level")},
        ),
        ("Period & Amount", {"fields": ("year", "month", "amount", "baseline_amount")}),
        ("AI & Integration", {"fields": ("is_ai_suggested", "recurring_series")}),
        (
            "Notes & Metadata",
            {
                "fields": ("user_note", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def period_display(self, obj):
        """Display period in readable format."""
        return obj.period_display

    period_display.short_description = "Period"
    period_display.admin_order_field = "year"

    def scope_display(self, obj):
        """Display budget scope clearly."""
        parts = []
        if obj.category:
            parts.append(f"📁 {obj.category.name}")
        if obj.subcategory:
            parts.append(f"→ {obj.subcategory.name}")
        if obj.payoree:
            parts.append(f"👤 {obj.payoree.name}")
        if obj.needs_level:
            parts.append(f"🏷️ {obj.needs_level.title()}")

        return " ".join(parts) if parts else "General"

    scope_display.short_description = "Scope"

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

        return format_html(
            '<span style="color: {};">{}{:.2f}</span>', color, sign, variance
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

        if variance > 0:
            color = "green"
            sign = "+"
        else:
            color = "red"
            sign = ""

        return format_html(
            '<span style="color: {};">{}{:.2f}</span>', color, sign, variance
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
