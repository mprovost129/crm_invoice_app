from django.contrib import admin

from .models import ProductService


@admin.register(ProductService)
class ProductServiceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "business",
        "item_type",
        "unit_label",
        "default_rate",
        "is_taxable",
        "is_active",
    )
    list_filter = ("item_type", "unit", "is_taxable", "is_active")
    search_fields = ("name", "description", "business__display_name")
    autocomplete_fields = ("business", "created_by")
    readonly_fields = ("is_active", "archived_at", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False
