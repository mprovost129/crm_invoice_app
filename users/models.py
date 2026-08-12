import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Email-first authentication model used by every project from this template."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = "customer / user"
        verbose_name_plural = "customers / users"
        ordering = ("last_name", "first_name", "email")
        constraints = [
            models.UniqueConstraint(
                Lower("email"), name="users_user_email_case_insensitive_unique"
            )
        ]

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def display_name(self):
        return self.get_full_name() or self.email

    @property
    def is_email_verified(self):
        return self.email_verified_at is not None

    def __str__(self):
        return self.display_name


class AccountProfile(models.Model):
    """Supplementary profile data for an authenticated account owner.

    This is separate from the future CRM Contact and tenant Business models.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_profile",
    )
    company_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    internal_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "account profile"
        verbose_name_plural = "account profiles"

    def __str__(self):
        return f"Profile for {self.user}"
