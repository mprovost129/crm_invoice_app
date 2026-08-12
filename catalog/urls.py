from django.urls import path

from .views import (
    CatalogCreateView,
    CatalogListView,
    CatalogStatusView,
    CatalogUpdateView,
)

app_name = "catalog"

urlpatterns = [
    path("app/catalog/", CatalogListView.as_view(), name="item-list"),
    path("app/catalog/new/", CatalogCreateView.as_view(), name="item-create"),
    path(
        "app/catalog/<uuid:item_id>/edit/",
        CatalogUpdateView.as_view(),
        name="item-update",
    ),
    path(
        "app/catalog/<uuid:item_id>/status/<str:action>/",
        CatalogStatusView.as_view(),
        name="item-status",
    ),
]
