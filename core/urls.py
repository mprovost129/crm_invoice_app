from django.urls import path

from .views import HomeView, health_check, liveness_check, readiness_check

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("health/", health_check, name="health"),
    path("health/live/", liveness_check, name="health-live"),
    path("health/ready/", readiness_check, name="health-ready"),
]
