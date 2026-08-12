from django.urls import path

from .views import (
    ContactCreateView,
    ContactDetailView,
    ContactListView,
    ContactNoteCreateView,
    ContactStatusView,
    ContactUpdateView,
)

app_name = "crm"

urlpatterns = [
    path("app/contacts/", ContactListView.as_view(), name="contact-list"),
    path("app/contacts/new/", ContactCreateView.as_view(), name="contact-create"),
    path(
        "app/contacts/<uuid:contact_id>/",
        ContactDetailView.as_view(),
        name="contact-detail",
    ),
    path(
        "app/contacts/<uuid:contact_id>/edit/",
        ContactUpdateView.as_view(),
        name="contact-update",
    ),
    path(
        "app/contacts/<uuid:contact_id>/status/<str:action>/",
        ContactStatusView.as_view(),
        name="contact-status",
    ),
    path(
        "app/contacts/<uuid:contact_id>/notes/",
        ContactNoteCreateView.as_view(),
        name="contact-note-create",
    ),
]
