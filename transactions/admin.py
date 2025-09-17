from urllib import request
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.db.models import Sum, Count
from django.http import HttpResponse
import csv
from datetime import datetime
from .models import (
    Transaction,
    Category,
    Payoree,
    Tag,
    LearnedSubcat,
    LearnedPayoree,
    KeywordRule,
    RecurringSeries,
)
from transactions.utils import trace
from django.db.models import Exists, OuterRef
from ingest.models import ScannedCheck  # wherever your model lives


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "bank_account",
        "sheet_account",
        "date",
        "description",
        "amount",
        "subcategory",
        "categorization_error",
        "parent_category",
        "account_type",
        "payoree",
        "primary_needs_level_display",
        "has_scanned_check",
    ]
    search_fields = ["description", "payoree__name", "bank_account__name"]
    list_filter = ["subcategory"]
    actions = ["export_csv", "export_all_csv"]

    def parent_category(self, obj):
        if obj.subcategory and obj.subcategory.parent:
            return obj.subcategory.parent.name
        return "—"

    parent_category.short_description = "Category"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            has_scanned_check=Exists(
                ScannedCheck.objects.filter(linked_transaction=OuterRef("pk"))
            )
        )

    def has_scanned_check(self, obj):
        return bool(getattr(obj, "has_scanned_check", False))

    has_scanned_check.boolean = True
    has_scanned_check.short_description = "Check image"

    def primary_needs_level_display(self, obj):
        """Display the primary needs level for this transaction."""
        if obj.needs_level:
            primary = obj.primary_needs_level()
            if len(obj.needs_level) == 1:
                return primary.title()
            else:
                # Show allocation for multi-level
                allocations = [f"{k.title()}: {v}%" for k, v in obj.needs_level.items()]
                return f"{primary.title()} ({', '.join(allocations)})"
        return "—"

    primary_needs_level_display.short_description = "Needs Level"

    def export_csv(self, request, queryset):
        """Export selected transactions to CSV with all fields."""
        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type="text/csv")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response["Content-Disposition"] = (
            f'attachment; filename="transactions_export_{timestamp}.csv"'
        )

        writer = csv.writer(response)

        # Write header row with all field names
        field_names = [
            "id",
            "source",
            "bank_account",
            "sheet_account",
            "date",
            "description",
            "amount",
            "account_type",
            "check_num",
            "payoree",
            "memo",
            "category",
            "subcategory",
            "categorization_error",
            "needs_level",
        ]
        writer.writerow(field_names)

        # Write data rows
        for transaction in queryset:
            row = [
                transaction.id,
                transaction.source,
                transaction.bank_account.name if transaction.bank_account else "",
                transaction.sheet_account,
                transaction.date.strftime("%Y-%m-%d") if transaction.date else "",
                transaction.description,
                str(transaction.amount),
                transaction.account_type,
                transaction.check_num or "",
                transaction.payoree.name if transaction.payoree else "",
                transaction.memo or "",
                transaction.category.name if transaction.category else "",
                transaction.subcategory.name if transaction.subcategory else "",
                transaction.categorization_error or "",
                str(transaction.needs_level) if transaction.needs_level else "",
            ]
            writer.writerow(row)

        return response

    export_csv.short_description = "Export selected transactions to CSV"

    def export_all_csv(self, request, queryset):
        """Export ALL transactions to CSV with all fields (ignores selection)."""
        # Get all transactions, not just selected ones
        all_transactions = (
            Transaction.objects.all()
            .select_related("bank_account", "payoree", "category", "subcategory")
            .order_by("date")
        )

        # Create the HttpResponse object with CSV header
        response = HttpResponse(content_type="text/csv")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response["Content-Disposition"] = (
            f'attachment; filename="transactions_all_export_{timestamp}.csv"'
        )

        writer = csv.writer(response)

        # Write header row with all field names
        field_names = [
            "id",
            "source",
            "bank_account",
            "sheet_account",
            "date",
            "description",
            "amount",
            "account_type",
            "check_num",
            "payoree",
            "memo",
            "category",
            "subcategory",
            "categorization_error",
            "needs_level",
        ]
        writer.writerow(field_names)

        # Write data rows
        for transaction in all_transactions:
            row = [
                transaction.id,
                transaction.source,
                transaction.bank_account.name if transaction.bank_account else "",
                transaction.sheet_account,
                transaction.date.strftime("%Y-%m-%d") if transaction.date else "",
                transaction.description,
                str(transaction.amount),
                transaction.account_type,
                transaction.check_num or "",
                transaction.payoree.name if transaction.payoree else "",
                transaction.memo or "",
                transaction.category.name if transaction.category else "",
                transaction.subcategory.name if transaction.subcategory else "",
                transaction.categorization_error or "",
                str(transaction.needs_level) if transaction.needs_level else "",
            ]
            writer.writerow(row)

        return response

    export_all_csv.short_description = "Export ALL transactions to CSV"


@admin.register(Payoree)
class PayoreeAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "default_category",
        "default_subcategory",
        "primary_needs_level_display",
        "transaction_count",
    ]
    search_fields = ["name"]
    list_filter = ["default_category", "default_subcategory"]
    actions = [
        "set_needs_level_critical",
        "set_needs_level_core",
        "set_needs_level_lifestyle",
        "set_needs_level_discretionary",
        "set_needs_level_luxury",
        "set_needs_level_deferred",
        "clear_needs_level",
    ]

    def primary_needs_level_display(self, obj):
        """Display the primary needs level for this payoree."""
        if obj.default_needs_level:
            primary = obj.primary_needs_level()
            if len(obj.default_needs_level) == 1:
                return primary.title()
            else:
                # Show allocation for multi-level
                allocations = [
                    f"{k.title()}: {v}%" for k, v in obj.default_needs_level.items()
                ]
                return f"{primary.title()} ({', '.join(allocations)})"
        return "—"

    primary_needs_level_display.short_description = "Needs Level"

    def transaction_count(self, obj):
        """Display the number of transactions for this payoree."""
        return obj.transaction_count

    transaction_count.short_description = "Transactions"

    # Bulk actions for setting needs levels
    def set_needs_level_critical(self, request, queryset):
        """Set selected payorees to Critical needs level."""
        updated = queryset.update(default_needs_level={"critical": 100})
        self.message_user(
            request, f"Successfully set {updated} payoree(s) to Critical needs level."
        )

    set_needs_level_critical.short_description = "Set needs level to Critical 100%%"

    def set_needs_level_core(self, request, queryset):
        """Set selected payorees to Core needs level."""
        updated = queryset.update(default_needs_level={"core": 100})
        self.message_user(
            request, f"Successfully set {updated} payoree(s) to Core needs level."
        )

    set_needs_level_core.short_description = "Set needs level to Core 100%%"

    def set_needs_level_lifestyle(self, request, queryset):
        """Set selected payorees to Lifestyle needs level."""
        updated = queryset.update(default_needs_level={"lifestyle": 100})
        self.message_user(
            request, f"Successfully set {updated} payoree(s) to Lifestyle needs level."
        )

    set_needs_level_lifestyle.short_description = "Set needs level to Lifestyle 100%%"

    def set_needs_level_discretionary(self, request, queryset):
        """Set selected payorees to Discretionary needs level."""
        updated = queryset.update(default_needs_level={"discretionary": 100})
        self.message_user(
            request,
            f"Successfully set {updated} payoree(s) to Discretionary needs level.",
        )

    set_needs_level_discretionary.short_description = (
        "Set needs level to Discretionary 100%%"
    )

    def set_needs_level_luxury(self, request, queryset):
        """Set selected payorees to Luxury needs level."""
        updated = queryset.update(default_needs_level={"luxury": 100})
        self.message_user(
            request, f"Successfully set {updated} payoree(s) to Luxury needs level."
        )

    set_needs_level_luxury.short_description = "Set needs level to Luxury 100%%"

    def set_needs_level_deferred(self, request, queryset):
        """Set selected payorees to Deferred needs level."""
        updated = queryset.update(default_needs_level={"deferred": 100})
        self.message_user(
            request, f"Successfully set {updated} payoree(s) to Deferred needs level."
        )

    set_needs_level_deferred.short_description = "Set needs level to Deferred 100%%"

    def clear_needs_level(self, request, queryset):
        """Clear the needs level for selected payorees."""
        updated = queryset.update(default_needs_level=None)
        self.message_user(
            request, f"Successfully cleared needs level for {updated} payoree(s)."
        )

    clear_needs_level.short_description = "Clear needs level"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "parent",
        "type",
        "category_transaction_count",
        "subcategory_transaction_count",
    ]
    search_fields = ["name", "type"]
    list_filter = ["parent", "type"]

    def get_queryset(self, request):
        """Override queryset to add transaction count annotations for sorting"""
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            category_count=Count("transactions_in_category", distinct=True),
            subcategory_count=Count("transactions_in_subcategory", distinct=True),
        )
        return queryset

    def category_transaction_count(self, obj):
        """Count transactions directly assigned to this category"""
        # Use the annotated value if available, otherwise fall back to direct count
        return getattr(obj, "category_count", obj.transactions_in_category.count())

    category_transaction_count.short_description = "Category Transactions"
    category_transaction_count.admin_order_field = "category_count"

    def subcategory_transaction_count(self, obj):
        """Count transactions assigned to this category as a subcategory"""
        # Use the annotated value if available, otherwise fall back to direct count
        return getattr(
            obj, "subcategory_count", obj.transactions_in_subcategory.count()
        )

    subcategory_transaction_count.short_description = "Subcategory Transactions"
    subcategory_transaction_count.admin_order_field = "subcategory_count"


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(LearnedSubcat)
class LearnedSubcatAdmin(admin.ModelAdmin):
    list_display = [
        "key",
        "subcategory",
        "parent_category",
        "count",
        "last_seen",
        "pattern_preview",
    ]
    list_filter = ["subcategory__parent", "subcategory", "last_seen"]
    search_fields = ["key", "subcategory__name", "subcategory__parent__name"]
    ordering = ["-count", "key"]
    list_display_links = ["key"]  # Make key clickable instead of editable

    def parent_category(self, obj):
        if obj.subcategory and obj.subcategory.parent:
            return obj.subcategory.parent.name
        return "—"

    parent_category.short_description = "Category"

    def pattern_preview(self, obj):
        """Show a preview of transactions that would match this pattern"""
        from .models import Transaction

        # Find up to 3 transactions that contain this key in their description
        matching_txns = Transaction.objects.filter(
            description__icontains=obj.key
        ).order_by("-date")[:3]

        if matching_txns:
            previews = []
            for txn in matching_txns:
                preview = f"{txn.date.strftime('%m/%d')} - {txn.description[:40]}..."
                previews.append(preview)
            return format_html("<br>".join(previews))
        return "No matching transactions found"

    pattern_preview.short_description = "Sample Transactions"

    actions = ["merge_patterns", "bulk_update_keys"]

    def merge_patterns(self, request, queryset):
        """Custom action to merge multiple patterns into one"""
        if queryset.count() < 2:
            self.message_user(request, "Select at least 2 patterns to merge.")
            return

        # This would redirect to a custom merge page
        selected = queryset.values_list("id", flat=True)
        return redirect(
            f'/admin/transactions/merge-patterns/?ids={",".join(map(str, selected))}'
        )

    merge_patterns.short_description = "Merge selected patterns"

    def bulk_update_keys(self, request, queryset):
        """Custom action for bulk key updates"""
        selected = queryset.values_list("id", flat=True)
        return redirect(
            f'/admin/transactions/bulk-update-keys/?ids={",".join(map(str, selected))}'
        )

    bulk_update_keys.short_description = "Bulk update keys"


@admin.register(LearnedPayoree)
class LearnedPayoreeAdmin(admin.ModelAdmin):
    list_display = ["key", "payoree", "count", "last_seen", "pattern_preview"]
    list_filter = ["payoree", "last_seen"]
    search_fields = ["key", "payoree__name"]
    ordering = ["-count", "key"]
    list_display_links = ["key"]  # Make key clickable instead of editable

    def pattern_preview(self, obj):
        """Show a preview of transactions that would match this pattern"""
        from .models import Transaction

        matching_txns = Transaction.objects.filter(
            description__icontains=obj.key
        ).order_by("-date")[:3]

        if matching_txns:
            previews = []
            for txn in matching_txns:
                preview = f"{txn.date.strftime('%m/%d')} - {txn.description[:40]}..."
                previews.append(preview)
            return format_html("<br>".join(previews))
        return "No matching transactions found"

    pattern_preview.short_description = "Sample Transactions"


@admin.register(KeywordRule)
class KeywordRuleAdmin(admin.ModelAdmin):
    list_display = [
        "keyword",
        "payoree",
        "category",
        "subcategory",
        "priority",
        "is_active",
        "created_by_user",
        "created_at",
    ]
    list_filter = ["category", "payoree", "is_active", "created_by_user", "priority"]
    search_fields = ["keyword", "category__name", "subcategory__name", "payoree__name"]
    ordering = ["-priority", "keyword"]
    list_editable = ["priority", "is_active"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for payoree field
        if "payoree" in form.base_fields:
            form.base_fields["payoree"].help_text = (
                "Optional: Automatically assign this payoree when keyword matches"
            )
        return form


@admin.register(RecurringSeries)
class RecurringSeriesAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "payoree",
        "amount_display",
        "interval",
        "active",
        "manually_disabled",
        "next_due",
    ]
    list_filter = ["active", "manually_disabled", "interval", "payoree"]
    search_fields = ["payoree__name"]
    readonly_fields = ["first_seen", "last_seen"]

    def amount_display(self, obj):
        # return decimal dollars
        try:
            return f"${obj.amount_cents/100:.2f}"
        except Exception:
            return None

    amount_display.short_description = "Amount"
    amount_display.admin_order_field = "amount_cents"
