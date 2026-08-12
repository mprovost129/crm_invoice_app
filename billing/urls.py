from django.urls import path

from .views import SubscriptionCheckoutView, SubscriptionView, platform_webhook

app_name = "billing"

urlpatterns = [
    path("settings/subscription/", SubscriptionView.as_view(), name="subscription"),
    path(
        "settings/subscription/checkout/",
        SubscriptionCheckoutView.as_view(),
        name="checkout",
    ),
    path("webhooks/stripe/platform/", platform_webhook, name="platform-webhook"),
]

