from django.contrib import admin
from .models import Transaction, Category

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['date', 'description', 'amount', 'subcategory', 'parent_category', 'payoree']
    search_fields = ['description', 'payoree']
    list_filter = ['subcategory']

    def parent_category(self, obj):
        if obj.subcategory and obj.subcategory.parent:
            return obj.subcategory.parent.name
        return "—"
    parent_category.short_description = "Category"


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent']
    search_fields = ['name']
    list_filter = ['parent']