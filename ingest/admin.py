from django.contrib import admin
from .models import FinancialAccount, ImportBatch, ImportRow, ScannedCheck


@admin.register(FinancialAccount)
class FinancialAccountAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


class ImportRowInline(admin.TabularInline):
    model = ImportRow
    extra = 0
    fields = ("row_index", "is_duplicate", "errors")


@admin.register(ImportBatch)
class ImportBatchAdmin(admin.ModelAdmin):
    list_display = ("id", "source_filename", "status", "row_count", "created_at")
    search_fields = ("source_filename",)
    inlines = [ImportRowInline]


@admin.register(ImportRow)
class ImportRowAdmin(admin.ModelAdmin):
    list_display = (
        "row_index",
        "raw",
        "norm_date",
        "norm_amount",
        "norm_description",
        "suggestions",
        "is_duplicate",
        "errors",
    )
    search_fields = ("norm_description", "norm_date" "norm_amount")


@admin.register(ScannedCheck)
class ScannedCheckAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "original_filename",
        "bank_account",
        "check_number",
        "amount",
        "created_at",
    )
    search_fields = ("original_filename", "bank_account", "check_number")
