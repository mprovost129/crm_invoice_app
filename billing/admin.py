from django.contrib import admin

from .models import Plan, PlatformWebhookEvent, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "monthly_price_cents", "is_active")
    list_filter = ("is_active",)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("workspace", "plan", "status", "billing_interval")
    list_filter = ("status", "plan")
    search_fields = ("workspace__name", "provider_customer_id")


@admin.register(PlatformWebhookEvent)
class PlatformWebhookEventAdmin(admin.ModelAdmin):
    list_display = ("provider_event_id", "event_type", "status", "created_at")
    list_filter = ("status", "event_type", "livemode")
    readonly_fields = tuple(field.name for field in PlatformWebhookEvent._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
