from django.contrib import admin

from .models import Contact, ContactNote


class ContactNoteInline(admin.TabularInline):
    model = ContactNote
    extra = 0
    can_delete = False
    fields = ("body", "created_by", "created_at")
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "company_name",
        "business",
        "status",
        "email",
        "phone",
        "updated_at",
    )
    list_filter = ("status", "country_code")
    search_fields = (
        "first_name",
        "last_name",
        "company_name",
        "email",
        "phone",
        "business__display_name",
    )
    autocomplete_fields = ("business", "created_by")
    readonly_fields = (
        "status",
        "status_before_archive",
        "converted_at",
        "archived_at",
        "created_at",
        "updated_at",
    )
    inlines = (ContactNoteInline,)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    list_display = ("contact", "business", "created_by", "created_at")
    search_fields = ("contact__first_name", "contact__last_name", "body")
    readonly_fields = (
        "business",
        "contact",
        "body",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.method in ("GET", "HEAD", "OPTIONS")

    def has_delete_permission(self, request, obj=None):
        return False
