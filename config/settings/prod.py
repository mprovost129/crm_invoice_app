import os

from config.env import bool_env, csv_env, validate_production_secret

from .base import *

DEBUG = False

ALLOWED_HOSTS = csv_env("ALLOWED_HOSTS", required=True)

validate_production_secret(SECRET_KEY)

# Whitenoise — insert after SecurityMiddleware
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

STORAGES = {
    "default": {
        # Override with a cloud storage backend in environments with ephemeral disks.
        "BACKEND": os.environ.get(
            "MEDIA_STORAGE_BACKEND",
            "django.core.files.storage.FileSystemStorage",
        ),
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Persistent DB connections
CONN_MAX_AGE = 60

CSRF_TRUSTED_ORIGINS = csv_env("CSRF_TRUSTED_ORIGINS")

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# HTTPS / security
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True


# Additional browser/security defaults.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
CONTENT_SECURITY_POLICY += "; upgrade-insecure-requests"

# Render and many other PaaS providers terminate TLS at a trusted reverse proxy.
# Enable only when your proxy sets X-Forwarded-Proto correctly.
if bool_env("TRUST_X_FORWARDED_PROTO"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
