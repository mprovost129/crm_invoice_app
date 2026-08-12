from django.urls import path

from .views import (
    EstimateConvertView,
    InvoiceCreateView,
    InvoiceDetailView,
    InvoiceEmailView,
    InvoiceIssueView,
    InvoiceLineCreateView,
    InvoiceLineDeleteView,
    InvoiceLineUpdateView,
    InvoiceListView,
    InvoicePDFView,
    InvoicePublicLinkView,
    InvoiceUpdateView,
    InvoiceVoidView,
    PaymentCreateView,
    PaymentReceiptView,
    PaymentReverseView,
    public_invoice_pdf,
    public_invoice_view,
)

app_name = "invoices"

urlpatterns = [
    path("app/invoices/", InvoiceListView.as_view(), name="list"),
    path("app/invoices/new/", InvoiceCreateView.as_view(), name="create"),
    path("app/invoices/<uuid:invoice_id>/", InvoiceDetailView.as_view(), name="detail"),
    path(
        "app/invoices/<uuid:invoice_id>/edit/",
        InvoiceUpdateView.as_view(),
        name="update",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/lines/new/",
        InvoiceLineCreateView.as_view(),
        name="line-create",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/lines/<uuid:line_id>/edit/",
        InvoiceLineUpdateView.as_view(),
        name="line-update",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/lines/<uuid:line_id>/delete/",
        InvoiceLineDeleteView.as_view(),
        name="line-delete",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/issue/",
        InvoiceIssueView.as_view(),
        name="issue",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/convert/",
        EstimateConvertView.as_view(),
        name="convert-estimate",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/email/",
        InvoiceEmailView.as_view(),
        name="email",
    ),
    path("app/invoices/<uuid:invoice_id>/pdf/", InvoicePDFView.as_view(), name="pdf"),
    path(
        "app/invoices/<uuid:invoice_id>/public-link/",
        InvoicePublicLinkView.as_view(),
        name="public-link",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/void/",
        InvoiceVoidView.as_view(),
        name="void",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/payments/",
        PaymentCreateView.as_view(),
        name="payment-create",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/payments/<uuid:payment_id>/reverse/",
        PaymentReverseView.as_view(),
        name="payment-reverse",
    ),
    path(
        "app/invoices/<uuid:invoice_id>/payments/<uuid:payment_id>/receipt/",
        PaymentReceiptView.as_view(),
        name="payment-receipt",
    ),
    path("i/<str:token>/", public_invoice_view, name="public-view"),
    path("i/<str:token>/pdf/", public_invoice_pdf, name="public-pdf"),
]
