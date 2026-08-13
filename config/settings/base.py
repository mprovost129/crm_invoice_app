import os
from pathlib import Path

from dotenv import load_dotenv

from config.env import bool_env, required_env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
# config/Settings/base.py -> .parent = Settings, .parent = config, .parent = project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")

# Generic application identity. Keep product names out of shared templates.
APP_NAME = os.environ.get("APP_NAME", "Django Application")
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "")

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = required_env("SECRET_KEY")

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "axes",
    # Local
    "users",
    "workspaces",
    "billing",
    "crm",
    "catalog",
    "activity",
    "estimates",
    "communications",
    "invoices",
    "payments",
    "dashboards",
    "core",
]

AUTH_USER_MODEL = "users.User"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.middleware.RequestIDMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "workspaces.middleware.TenantContextMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Axes — brute-force login protection
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_CALLABLE = None  # uses default 403 response

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                "core.context_processors.application",
                "workspaces.context_processors.tenant_context",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = os.environ.get("LANGUAGE_CODE", "en-us")
TIME_ZONE = os.environ.get("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [BASE_DIR / "locale"]

# Static files
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files
MEDIA_URL = os.environ.get("MEDIA_URL", "media/")
MEDIA_ROOT = BASE_DIR / "media"

# Upload limits are generic safety rails and can be overridden per project.
DATA_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)
)
FILE_UPLOAD_MAX_MEMORY_SIZE = int(
    os.environ.get("FILE_UPLOAD_MAX_MEMORY_SIZE", 5 * 1024 * 1024)
)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Auth
LOGIN_URL = "users:login"
LOGIN_REDIRECT_URL = "/app/"
LOGOUT_REDIRECT_URL = "/"

# Cache — overridden per environment
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "filters": {
        "sensitive_data": {"()": "core.logging.SensitiveDataFilter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["sensitive_data"],
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": os.environ.get("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
    },
}

# Database
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_env("DB_NAME"),
        "USER": required_env("DB_USER"),
        "PASSWORD": required_env("DB_PASSWORD"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# Email
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "webmaster@localhost")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", 10))
PASSWORD_RESET_TIMEOUT = int(os.environ.get("PASSWORD_RESET_TIMEOUT", 24 * 60 * 60))
PUBLIC_DOCUMENT_LINK_TTL_DAYS = int(os.environ.get("PUBLIC_DOCUMENT_LINK_TTL_DAYS", 90))
PUBLIC_DOCUMENT_VIEW_LIMIT = int(os.environ.get("PUBLIC_DOCUMENT_VIEW_LIMIT", 120))
PUBLIC_PAYMENT_ATTEMPT_LIMIT = int(os.environ.get("PUBLIC_PAYMENT_ATTEMPT_LIMIT", 20))
PUBLIC_ACCOUNT_CREATE_LIMIT = int(os.environ.get("PUBLIC_ACCOUNT_CREATE_LIMIT", 10))
PUBLIC_EMAIL_SEND_LIMIT = int(os.environ.get("PUBLIC_EMAIL_SEND_LIMIT", 5))

CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "form-action 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "style-src-elem 'self' https://cdn.jsdelivr.net",
        "style-src-attr 'unsafe-inline'",
        "script-src 'self' https://cdn.jsdelivr.net",
        "connect-src 'self'",
    )
)

# Stripe Billing and Stripe Connect use the same platform secret key but deliberately
# separate webhook endpoints and signing secrets.
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_PLATFORM_WEBHOOK_SECRET = os.environ.get("STRIPE_PLATFORM_WEBHOOK_SECRET", "")
STRIPE_CONNECT_WEBHOOK_SECRET = os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET", "")
STRIPE_LIVE_MODE = bool_env("STRIPE_LIVE_MODE", default=False)
