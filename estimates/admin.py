from django.contrib import admin

from .models import Estimate, EstimateAcceptance, EstimateLineItem


class EstimateLineItemInline(admin.TabularInline):
    model = EstimateLineItem
    extra = 0
    can_delete = False
    fields = (
        "position",
        "name",
        "quantity",
        "unit_rate",
        "tax_amount",
        "line_total",
    )
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Estimate)
class EstimateAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "contact",
        "business",
        "status",
        "currency",
        "total",
        "expiration_date",
        "updated_at",
    )
    list_filter = ("status", "currency", "requires_acceptance")
    search_fields = (
        "number",
        "contact__first_name",
        "contact__last_name",
        "contact__company_name",
        "business__display_name",
    )
    readonly_fields = tuple(field.name for field in Estimate._meta.fields)
    inlines = (EstimateLineItemInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EstimateLineItem)
class EstimateLineItemAdmin(admin.ModelAdmin):
    list_display = ("estimate", "position", "name", "quantity", "line_total")
    search_fields = ("estimate__number", "name")
    readonly_fields = tuple(field.name for field in EstimateLineItem._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EstimateAcceptance)
class EstimateAcceptanceAdmin(admin.ModelAdmin):
    list_display = ("estimate", "method", "accepted_at", "accepted_by_name")
    search_fields = ("estimate__number", "accepted_by_name", "accepted_by_email")
    readonly_fields = tuple(field.name for field in EstimateAcceptance._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
