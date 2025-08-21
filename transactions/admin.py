from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.shortcuts import redirect
from django.db.models import Sum
from .models import Transaction, Category, Payoree, Tag, LearnedSubcat, LearnedPayoree, KeywordRule

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['bank_account','date', 'description', 'amount', 'subcategory', 'categorization_error', 'parent_category', 'account_type','payoree']
    search_fields = ['description', 'payoree']
    list_filter = ['subcategory']

    def parent_category(self, obj):
        if obj.subcategory and obj.subcategory.parent:
            return obj.subcategory.parent.name
        return "—"
    parent_category.short_description = "Category"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'type']
    search_fields = ['name',type]
    list_filter = ['parent','type']

@admin.register(Payoree)
class PayoreeAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    ordering = ['name']

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']
    ordering = ['name']


@admin.register(LearnedSubcat)
class LearnedSubcatAdmin(admin.ModelAdmin):
    list_display = ['key', 'subcategory', 'parent_category', 'count', 'last_seen', 'pattern_preview']
    list_filter = ['subcategory__parent', 'subcategory', 'last_seen']
    search_fields = ['key', 'subcategory__name', 'subcategory__parent__name']
    ordering = ['-count', 'key']
    list_display_links = ['key']  # Make key clickable instead of editable
    
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
        ).order_by('-date')[:3]
        
        if matching_txns:
            previews = []
            for txn in matching_txns:
                preview = f"{txn.date.strftime('%m/%d')} - {txn.description[:40]}..."
                previews.append(preview)
            return format_html('<br>'.join(previews))
        return "No matching transactions found"
    pattern_preview.short_description = "Sample Transactions"
    
    actions = ['merge_patterns', 'bulk_update_keys']
    
    def merge_patterns(self, request, queryset):
        """Custom action to merge multiple patterns into one"""
        if queryset.count() < 2:
            self.message_user(request, "Select at least 2 patterns to merge.")
            return
        
        # This would redirect to a custom merge page
        selected = queryset.values_list('id', flat=True)
        return redirect(f'/admin/transactions/merge-patterns/?ids={",".join(map(str, selected))}')
    merge_patterns.short_description = "Merge selected patterns"
    
    def bulk_update_keys(self, request, queryset):
        """Custom action for bulk key updates"""
        selected = queryset.values_list('id', flat=True) 
        return redirect(f'/admin/transactions/bulk-update-keys/?ids={",".join(map(str, selected))}')
    bulk_update_keys.short_description = "Bulk update keys"


@admin.register(LearnedPayoree) 
class LearnedPayoreeAdmin(admin.ModelAdmin):
    list_display = ['key', 'payoree', 'count', 'last_seen', 'pattern_preview']
    list_filter = ['payoree', 'last_seen']
    search_fields = ['key', 'payoree__name']
    ordering = ['-count', 'key']
    list_display_links = ['key']  # Make key clickable instead of editable
    
    def pattern_preview(self, obj):
        """Show a preview of transactions that would match this pattern"""
        from .models import Transaction
        matching_txns = Transaction.objects.filter(
            description__icontains=obj.key
        ).order_by('-date')[:3]
        
        if matching_txns:
            previews = []
            for txn in matching_txns:
                preview = f"{txn.date.strftime('%m/%d')} - {txn.description[:40]}..."
                previews.append(preview)
            return format_html('<br>'.join(previews))
        return "No matching transactions found"
    pattern_preview.short_description = "Sample Transactions"


@admin.register(KeywordRule)
class KeywordRuleAdmin(admin.ModelAdmin):
    list_display = ['keyword', 'payoree', 'category', 'subcategory', 'priority', 'is_active', 'created_by_user', 'created_at']
    list_filter = ['category', 'payoree', 'is_active', 'created_by_user', 'priority']
    search_fields = ['keyword', 'category__name', 'subcategory__name', 'payoree__name']
    ordering = ['-priority', 'keyword']
    list_editable = ['priority', 'is_active']
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Add help text for payoree field
        if 'payoree' in form.base_fields:
            form.base_fields['payoree'].help_text = 'Optional: Automatically assign this payoree when keyword matches'
        return form
