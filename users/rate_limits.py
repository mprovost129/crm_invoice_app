import hashlib

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


class RateLimitedPostMixin:
    rate_limit_setting = None
    rate_limit_window = 3600

    def dispatch(self, request, *args, **kwargs):
        if request.method == "POST":
            identity = request.META.get("REMOTE_ADDR", "unknown")
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            action = f"{self.__class__.__module__}.{self.__class__.__name__}"
            key = f"public-post-rate:{action}:{digest}"
            limit = getattr(settings, self.rate_limit_setting)
            if cache.add(key, 1, timeout=self.rate_limit_window):
                attempts = 1
            else:
                try:
                    attempts = cache.incr(key)
                except ValueError:
                    cache.set(key, 1, timeout=self.rate_limit_window)
                    attempts = 1
            if attempts > limit:
                response = HttpResponse("Too many requests.", status=429)
                response["Retry-After"] = str(self.rate_limit_window)
                return response
        return super().dispatch(request, *args, **kwargs)
