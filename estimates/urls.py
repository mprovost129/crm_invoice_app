from django.urls import path

from .views import (
    EstimateCreateView,
    EstimateDetailView,
    EstimateEmailView,
    EstimateIssueView,
    EstimateLineCreateView,
    EstimateLineDeleteView,
    EstimateLineUpdateView,
    EstimateListView,
    EstimateManualAcceptanceView,
    EstimatePDFView,
    EstimatePublicLinkView,
    EstimateUpdateView,
    public_estimate_pdf,
    public_estimate_respond,
    public_estimate_view,
)

app_name = "estimates"

urlpatterns = [
    path("app/estimates/", EstimateListView.as_view(), name="list"),
    path("app/estimates/new/", EstimateCreateView.as_view(), name="create"),
    path(
        "app/estimates/<uuid:estimate_id>/", EstimateDetailView.as_view(), name="detail"
    ),
    path(
        "app/estimates/<uuid:estimate_id>/edit/",
        EstimateUpdateView.as_view(),
        name="update",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/lines/new/",
        EstimateLineCreateView.as_view(),
        name="line-create",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/lines/<uuid:line_id>/edit/",
        EstimateLineUpdateView.as_view(),
        name="line-update",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/lines/<uuid:line_id>/delete/",
        EstimateLineDeleteView.as_view(),
        name="line-delete",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/issue/",
        EstimateIssueView.as_view(),
        name="issue",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/email/",
        EstimateEmailView.as_view(),
        name="email",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/pdf/", EstimatePDFView.as_view(), name="pdf"
    ),
    path(
        "app/estimates/<uuid:estimate_id>/public-link/",
        EstimatePublicLinkView.as_view(),
        name="public-link",
    ),
    path(
        "app/estimates/<uuid:estimate_id>/manual-acceptance/",
        EstimateManualAcceptanceView.as_view(),
        name="manual-acceptance",
    ),
    path("e/<str:token>/", public_estimate_view, name="public-view"),
    path("e/<str:token>/respond/", public_estimate_respond, name="public-respond"),
    path("e/<str:token>/pdf/", public_estimate_pdf, name="public-pdf"),
]
