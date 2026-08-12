from django.contrib import admin

from .models import (
    ConnectedAccount,
    ConnectWebhookEvent,
    InvoicePaymentAttempt,
    Payment,
    PaymentReversal,
)


class ReadOnlyLedgerAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Payment)
class PaymentAdmin(ReadOnlyLedgerAdmin):
    list_display = ("invoice", "amount", "currency", "paid_on", "method", "posted_at")
    list_filter = ("source", "method", "paid_on")
    search_fields = ("invoice__number", "reference", "business__display_name")
    readonly_fields = tuple(field.name for field in Payment._meta.fields)


@admin.register(PaymentReversal)
class PaymentReversalAdmin(ReadOnlyLedgerAdmin):
    list_display = ("payment", "amount", "reversed_at", "recorded_by")
    search_fields = ("payment__invoice__number", "reason")
    readonly_fields = tuple(field.name for field in PaymentReversal._meta.fields)


@admin.register(ConnectedAccount)
class ConnectedAccountAdmin(admin.ModelAdmin):
    list_display = ("business", "status", "charges_enabled", "payouts_enabled")
    list_filter = ("status", "charges_enabled", "payouts_enabled")
    readonly_fields = ("provider_account_id", "provider_synced_at")


@admin.register(InvoicePaymentAttempt)
class InvoicePaymentAttemptAdmin(ReadOnlyLedgerAdmin):
    list_display = ("invoice", "amount", "currency", "status", "created_at")
    list_filter = ("status", "currency")
    readonly_fields = tuple(field.name for field in InvoicePaymentAttempt._meta.fields)


@admin.register(ConnectWebhookEvent)
class ConnectWebhookEventAdmin(ReadOnlyLedgerAdmin):
    list_display = ("provider_event_id", "event_type", "status", "created_at")
    list_filter = ("status", "event_type", "livemode")
    readonly_fields = tuple(field.name for field in ConnectWebhookEvent._meta.fields)
