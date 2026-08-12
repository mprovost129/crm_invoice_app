from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html, format_html_join
from django.utils.translation import gettext_lazy as _

from .forms import UserChangeForm, UserCreationForm
from .models import AccountProfile, User


class AccountProfileInline(admin.StackedInline):
    model = AccountProfile
    extra = 0
    max_num = 1
    can_delete = False
    verbose_name_plural = "Customer profile"
    fields = ("company_name", "phone", "internal_notes", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Customer-centric support console built on Django's standard UserAdmin."""

    form = UserChangeForm
    add_form = UserCreationForm
    inlines = (AccountProfileInline,)

    ordering = ("last_name", "first_name", "email")
    list_display = (
        "customer_name",
        "email",
        "company",
        "account_status",
        "is_staff",
        "date_joined",
        "last_login",
    )
    list_display_links = ("customer_name", "email")
    list_filter = ("is_active", "is_staff", "is_superuser", "date_joined", "last_login")
    search_fields = (
        "email",
        "first_name",
        "last_name",
        "account_profile__company_name",
        "account_profile__phone",
    )
    list_select_related = ("account_profile",)
    date_hierarchy = "date_joined"
    list_per_page = 50
    save_on_top = True

    fieldsets = (
        (_("Customer"), {"fields": ("email", "first_name", "last_name", "password")}),
        (_("Account status"), {"fields": ("is_active", "last_login", "date_joined")}),
        (
            _("Related customer records"),
            {
                "fields": ("related_customer_records",),
                "description": (
                    "Automatically lists records in other apps that point directly to this user. "
                    "Subscriptions, projects, orders, events, and similar models will appear here "
                    "when they use settings.AUTH_USER_MODEL."
                ),
            },
        ),
        (
            _("Staff permissions"),
            {
                "classes": ("collapse",),
                "fields": ("is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "is_active",
                    "is_staff",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined", "related_customer_records")

    @admin.display(description="Customer", ordering="last_name")
    def customer_name(self, obj):
        return obj.get_full_name() or "—"

    @admin.display(description="Company", ordering="account_profile__company_name")
    def company(self, obj):
        try:
            return obj.account_profile.company_name or "—"
        except AccountProfile.DoesNotExist:
            return "—"

    @admin.display(description="Status", boolean=True, ordering="is_active")
    def account_status(self, obj):
        return obj.is_active

    @admin.display(description="Related records")
    def related_customer_records(self, obj):
        if not obj or not obj.pk:
            return "Save the customer first."

        rows = []
        ignored_models = {"logentry", "accountprofile"}

        for relation in obj._meta.related_objects:
            model = relation.related_model
            if model._meta.model_name in ignored_models:
                continue

            accessor_name = relation.get_accessor_name()
            if not accessor_name:
                continue

            try:
                query_name = relation.field.name
                count = model._default_manager.filter(**{query_name: obj}).count()
            except (AttributeError, TypeError):
                continue

            label = model._meta.verbose_name_plural.title()
            try:
                url = reverse(
                    f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist"
                )
                url = f"{url}?{query_name}__id__exact={obj.pk}"
                value = format_html('<a href="{}">{} ({})</a>', url, label, count)
            except NoReverseMatch:
                value = f"{label} ({count})"

            rows.append((value,))

        if not rows:
            return "No related project records yet."

        return format_html_join("", "<div class='customer-related-row'>{}</div>", rows)


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    """Advanced/raw profile access. Day-to-day support should start from Customers / Users."""

    list_display = ("user", "company_name", "phone", "updated_at")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "company_name",
        "phone",
    )
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")


admin.site.site_header = "Application Administration"
admin.site.site_title = "Admin"
admin.site.index_title = "Customer Support Dashboard"
admin.site.index_template = "admin/customer_index.html"
