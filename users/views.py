from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.views import View
from django.views.generic import FormView, TemplateView

from workspaces.models import Business

from .forms import RegistrationForm, ResendVerificationForm
from .models import User
from .rate_limits import RateLimitedPostMixin
from .services import register_user, send_verification_email
from .tokens import email_verification_token


def post_login_destination(user):
    if not user.is_email_verified:
        return reverse("users:verification-sent")
    if not Business.objects.for_user(user).active().exists():
        return reverse("workspaces:onboarding")
    return reverse("workspaces:dashboard")


class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_success_url(self):
        destination = post_login_destination(self.request.user)
        if destination != reverse("workspaces:dashboard"):
            return destination
        return super().get_success_url()


class RegistrationView(RateLimitedPostMixin, FormView):
    template_name = "registration/register.html"
    form_class = RegistrationForm
    success_url = reverse_lazy("users:verification-sent")
    rate_limit_setting = "PUBLIC_ACCOUNT_CREATE_LIMIT"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(post_login_destination(request.user))
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = register_user(
            email=form.cleaned_data["email"],
            password=form.cleaned_data["password1"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
        )
        self.request.session["verification_user_id"] = str(user.pk)
        messages.success(
            self.request,
            "Your account was created. Check your email to verify it.",
        )
        return super().form_valid(form)


class VerificationSentView(TemplateView):
    template_name = "registration/verification_sent.html"


class VerifyEmailView(View):
    def get(self, request, uidb64, token):
        try:
            user_id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=user_id, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist) as exc:
            raise Http404("Invalid verification link.") from exc

        if not email_verification_token.check_token(user, token):
            return TemplateView.as_view(
                template_name="registration/verification_invalid.html"
            )(request)

        if not user.is_email_verified:
            user.email_verified_at = timezone.now()
            user.save(update_fields=("email_verified_at",))

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.pop("verification_user_id", None)
        messages.success(request, "Your email address is verified.")
        return redirect(post_login_destination(user))


class ResendVerificationView(RateLimitedPostMixin, FormView):
    template_name = "registration/resend_verification.html"
    form_class = ResendVerificationForm
    success_url = reverse_lazy("users:verification-sent")
    rate_limit_setting = "PUBLIC_EMAIL_SEND_LIMIT"

    def form_valid(self, form):
        user = User.objects.filter(email__iexact=form.cleaned_data["email"]).first()
        if user and user.is_active and not user.is_email_verified:
            send_verification_email(user.pk)
        messages.success(
            self.request,
            "If an unverified account exists, a new verification email has been sent.",
        )
        return super().form_valid(form)


class AccountRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        return redirect(post_login_destination(request.user))


class PasswordResetView(RateLimitedPostMixin, auth_views.PasswordResetView):
    template_name = "registration/password_reset.html"
    email_template_name = "registration/password_reset_email.html"
    subject_template_name = "registration/password_reset_subject.txt"
    extra_email_context = {"app_name": settings.APP_NAME}
    success_url = reverse_lazy("users:password_reset_done")
    rate_limit_setting = "PUBLIC_EMAIL_SEND_LIMIT"
