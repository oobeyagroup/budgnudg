from urllib import request
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.db.models import Sum, Count
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
        "date",
        "description",
        "amount",
        "subcategory",
        "categorization_error",
        "parent_category",
        "account_type",
        "payoree",
        "has_scanned_check",
    ]
    search_fields = ["description", "payoree__name", "bank_account__name"]
    list_filter = ["subcategory"]

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


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = [
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


@admin.register(Payoree)
class PayoreeAdmin(admin.ModelAdmin):
    list_display = ["name", "transaction_count"]
    search_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self, request):
        """Override queryset to add transaction count annotation for sorting"""
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(trans_count=Count("transaction", distinct=True))
        return queryset

    def transaction_count(self, obj):
        """Count transactions assigned to this payoree"""
        # Use the annotated value if available, otherwise fall back to direct count
        return getattr(obj, "trans_count", obj.transaction_set.count())

    transaction_count.short_description = "Transactions"
    transaction_count.admin_order_field = "trans_count"


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
        "next_due",
    ]
    list_filter = ["active", "interval", "payoree"]
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
