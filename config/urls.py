from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("users.urls")),
    path("", include("workspaces.urls")),
    path("", include("crm.urls")),
    path("", include("catalog.urls")),
    path("", include("estimates.urls")),
    path("", include("invoices.urls")),
    path("", include("dashboards.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
