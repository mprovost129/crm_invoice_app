from django.urls import path

from .views import BusinessOnboardingView, BusinessSettingsView, DashboardView

app_name = "workspaces"

urlpatterns = [
    path("app/", DashboardView.as_view(), name="dashboard"),
    path("onboarding/business/", BusinessOnboardingView.as_view(), name="onboarding"),
    path("settings/business/", BusinessSettingsView.as_view(), name="settings"),
]
