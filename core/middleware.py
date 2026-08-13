import re
import uuid

from django.conf import settings

SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIDMiddleware:
    """Attach a correlation ID to every request and response for support/debugging."""

    header_name = "HTTP_X_REQUEST_ID"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied_id = request.META.get(self.header_name, "")
        request.request_id = (
            supplied_id if SAFE_REQUEST_ID.fullmatch(supplied_id) else uuid.uuid4().hex
        )
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class SecurityHeadersMiddleware:
    """Apply the reviewed browser policy to every application response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        return response
