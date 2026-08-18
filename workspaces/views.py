from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.generic import FormView, TemplateView

from dashboards.selectors import (
    dashboard_summary,
    needs_attention,
    recent_activity,
    unread_notifications,
)

from .forms import BusinessDefaultsForm, BusinessOnboardingForm, BusinessProfileForm
from .mixins import OwnerTenantRequiredMixin, VerifiedUserMixin
from .selectors import active_owner_membership_for_user
from .services import complete_business_onboarding, update_business_configuration


class DashboardView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "dashboards/dashboard.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "summary": dashboard_summary(business=self.request.business),
            "attention_items": needs_attention(business=self.request.business),
            "recent_activity": recent_activity(business=self.request.business),
            "notifications": unread_notifications(
                business=self.request.business, recipient=self.request.user
            ),
        }


class BusinessOnboardingView(VerifiedUserMixin, FormView):
    template_name = "workspaces/onboarding.html"
    form_class = BusinessOnboardingForm

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_staff
            and active_owner_membership_for_user(request.user) is None
        ):
            messages.info(
                request,
                "Staff accounts without a customer workspace use the administration site.",
            )
            return redirect("admin:index")
        if getattr(request, "business", None) is not None:
            return redirect("workspaces:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial.update(
            {
                "owner_name": self.request.user.display_name,
                "email": self.request.user.email,
            }
        )
        return initial

    def form_valid(self, form):
        try:
            business = complete_business_onboarding(
                actor=self.request.user,
                data=form.cleaned_data,
            )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        self.request.business = business
        messages.success(self.request, "Your business is ready.")
        return redirect("workspaces:dashboard")


class BusinessSettingsView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "workspaces/settings.html"

    def get(self, request, *args, **kwargs):
        return render(
            request,
            self.template_name,
            {
                "profile_form": BusinessProfileForm(
                    instance=request.business,
                    prefix="profile",
                ),
                "defaults_form": BusinessDefaultsForm(
                    business=request.business,
                    prefix="defaults",
                ),
            },
        )

    def post(self, request, *args, **kwargs):
        profile_form = BusinessProfileForm(
            request.POST,
            request.FILES,
            instance=request.business,
            prefix="profile",
        )
        defaults_form = BusinessDefaultsForm(
            request.POST,
            business=request.business,
            prefix="defaults",
        )
        if profile_form.is_valid() and defaults_form.is_valid():
            profile_fields = {
                field: profile_form.cleaned_data[field]
                for field in profile_form.Meta.fields
            }
            update_business_configuration(
                actor=request.user,
                business_id=request.business.pk,
                profile_data=profile_fields,
                defaults_data=defaults_form.cleaned_data,
            )
            messages.success(request, "Business settings updated.")
            return redirect("workspaces:settings")

        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form,
                "defaults_form": defaults_form,
            },
            status=400,
        )
