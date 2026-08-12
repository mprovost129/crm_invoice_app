from django.urls import path

from .views import (
    CommunicationsView,
    ExportView,
    NotificationReadView,
    ReportsView,
)

app_name = "dashboards"

urlpatterns = [
    path("app/reports/", ReportsView.as_view(), name="reports"),
    path("app/communications/", CommunicationsView.as_view(), name="communications"),
    path(
        "app/notifications/<uuid:notification_id>/read/",
        NotificationReadView.as_view(),
        name="notification-read",
    ),
    path("app/exports/<str:export_type>.csv", ExportView.as_view(), name="export"),
]
