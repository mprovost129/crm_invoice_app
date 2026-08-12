from django.contrib import admin

from .models import ActivityEvent


@admin.register(ActivityEvent)
class ActivityEventAdmin(admin.ModelAdmin):
    list_display = ("occurred_at", "business", "event_type", "summary", "actor")
    list_filter = ("event_type", "occurred_at")
    search_fields = (
        "summary",
        "business__display_name",
        "contact__first_name",
        "contact__last_name",
        "product_service__name",
        "estimate__number",
    )
    readonly_fields = (
        "business",
        "actor",
        "contact",
        "product_service",
        "estimate",
        "event_type",
        "summary",
        "metadata",
        "occurred_at",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
