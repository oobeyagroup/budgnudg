from django.contrib import admin
from .models import Transaction, Category

# Register your models here.


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "date", "description", "amount", "category",)
    search_fields = ("description",)
    list_filter = ("category",)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ("name",)