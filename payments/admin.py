from django.contrib import admin

from .models import Payment, PaymentReversal


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
