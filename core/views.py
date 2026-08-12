from django.db import connection
from django.http import JsonResponse
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "core/home.html"


def liveness_check(request):
    """Report that the Django process can serve requests."""
    return JsonResponse({"status": "ok", "application": "ok"})


def readiness_check(request):
    """Report whether Django can reach its required primary database."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {"status": "unhealthy", "database": "unavailable"}, status=503
        )

    return JsonResponse({"status": "ok", "database": "ok"})


health_check = readiness_check
