from django.urls import path

from .views import (
    ConnectOnboardingView,
    ConnectRefreshView,
    ConnectReturnView,
    CreateInvoicePaymentLinkView,
    PaymentSettingsView,
    connect_webhook,
    payment_return,
    public_payment,
)

app_name = "payments"

urlpatterns = [
    path("settings/payments/", PaymentSettingsView.as_view(), name="settings"),
    path("settings/payments/connect/", ConnectOnboardingView.as_view(), name="connect"),
    path(
        "settings/payments/connect/refresh/",
        ConnectRefreshView.as_view(),
        name="connect-refresh",
    ),
    path(
        "settings/payments/connect/return/",
        ConnectReturnView.as_view(),
        name="connect-return",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/payment-link/",
        CreateInvoicePaymentLinkView.as_view(),
        name="invoice-payment-link",
    ),
    path("p/payment/return/", payment_return, name="payment-return"),
    path("p/<str:token>/", public_payment, name="public-payment"),
    path("webhooks/stripe/connect/", connect_webhook, name="connect-webhook"),
]
