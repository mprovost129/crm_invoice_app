from django.contrib import admin

from .models import Invoice, InvoiceLineItem


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 0
    can_delete = False
    fields = ("position", "name", "quantity", "unit_rate", "tax_amount", "line_total")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "contact",
        "business",
        "status",
        "currency",
        "total",
        "amount_paid",
        "balance_due",
        "due_date",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "number",
        "contact__first_name",
        "contact__last_name",
        "contact__company_name",
        "business__display_name",
    )
    readonly_fields = tuple(field.name for field in Invoice._meta.fields)
    inlines = (InvoiceLineItemInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ("invoice", "position", "name", "quantity", "line_total")
    search_fields = ("invoice__number", "name")
    readonly_fields = tuple(field.name for field in InvoiceLineItem._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
