from django.conf import settings


def application(request):
    """Expose generic application identity without hard-coding product names in templates."""
    return {
        "APP_NAME": settings.APP_NAME,
        "SITE_URL": settings.SITE_URL,
        "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
    }
