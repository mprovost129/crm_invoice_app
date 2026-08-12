from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.generic import FormView, TemplateView

from .forms import BusinessDefaultsForm, BusinessOnboardingForm, BusinessProfileForm
from .mixins import OwnerTenantRequiredMixin, VerifiedUserMixin
from .services import complete_business_onboarding, update_business_configuration


class DashboardView(OwnerTenantRequiredMixin, TemplateView):
    template_name = "workspaces/dashboard.html"


class BusinessOnboardingView(VerifiedUserMixin, FormView):
    template_name = "workspaces/onboarding.html"
    form_class = BusinessOnboardingForm

    def dispatch(self, request, *args, **kwargs):
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
