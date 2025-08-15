from django.contrib import admin
from .models import Transaction, Category, Payoree, Tag

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
