from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from .views import (
    AccountRedirectView,
    LoginView,
    PasswordResetView,
    RegistrationView,
    ResendVerificationView,
    VerificationSentView,
    VerifyEmailView,
)

app_name = "users"

urlpatterns = [
    path("", AccountRedirectView.as_view(), name="account"),
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "verify-email/",
        VerificationSentView.as_view(),
        name="verification-sent",
    ),
    path(
        "verify-email/resend/",
        ResendVerificationView.as_view(),
        name="resend-verification",
    ),
    path(
        "verify-email/<uidb64>/<token>/",
        VerifyEmailView.as_view(),
        name="verify-email",
    ),
    path(
        "password-reset/",
        PasswordResetView.as_view(),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html",
            success_url=reverse_lazy("users:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/done/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
]
