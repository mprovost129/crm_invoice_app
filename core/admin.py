from django.contrib import admin

from .models import DocumentSequence


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(admin.ModelAdmin):
    list_display = ("business", "document_type", "prefix", "next_value", "updated_at")
    list_filter = ("document_type",)
    search_fields = ("business__display_name", "business__workspace__name", "prefix")
    readonly_fields = (
        "business",
        "document_type",
        "prefix",
        "next_value",
        "padding_width",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
