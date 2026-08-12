from django.contrib import admin

from .models import Business, BusinessSettings, Membership, Workspace


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    fields = ("user", "role", "status", "accepted_at")
    autocomplete_fields = ("user",)


class BusinessInline(admin.TabularInline):
    model = Business
    extra = 0
    fields = ("display_name", "is_active", "default_currency", "timezone")
    show_change_link = True


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "owner_user", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "slug", "owner_user__email")
    autocomplete_fields = ("owner_user",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (MembershipInline, BusinessInline)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "workspace", "role", "status", "accepted_at")
    list_filter = ("role", "status")
    search_fields = ("user__email", "workspace__name")
    autocomplete_fields = ("user", "workspace")
    readonly_fields = ("created_at", "updated_at")


class BusinessSettingsInline(admin.StackedInline):
    model = BusinessSettings
    extra = 0
    max_num = 1
    can_delete = False


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "workspace",
        "default_currency",
        "timezone",
        "is_active",
    )
    list_filter = ("is_active", "default_currency", "country_code")
    search_fields = ("display_name", "legal_name", "email", "workspace__name")
    autocomplete_fields = ("workspace",)
    readonly_fields = ("created_at", "updated_at", "archived_at")
    inlines = (BusinessSettingsInline,)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ("business", "estimate_prefix", "invoice_prefix", "updated_at")
    search_fields = ("business__display_name", "business__workspace__name")
    autocomplete_fields = ("business",)
    readonly_fields = ("created_at", "updated_at")
