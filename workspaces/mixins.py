from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse

from .models import Membership


class VerifiedUserMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_email_verified:
            messages.info(request, "Verify your email address to continue.")
            return redirect("users:verification-sent")
        return super().dispatch(request, *args, **kwargs)


class TenantRequiredMixin(VerifiedUserMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_email_verified:
            if getattr(request, "business", None) is None:
                return redirect(reverse("workspaces:onboarding"))
        return super().dispatch(request, *args, **kwargs)


class OwnerTenantRequiredMixin(TenantRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and request.user.is_email_verified
            and getattr(request, "business", None) is not None
            and (
                request.membership is None
                or request.membership.role != Membership.Role.OWNER
                or request.membership.workspace_id != request.business.workspace_id
            )
        ):
            raise PermissionDenied("Workspace owner access is required.")
        return super().dispatch(request, *args, **kwargs)
