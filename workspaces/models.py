import uuid
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    FileExtensionValidator,
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel

document_prefix_validator = RegexValidator(
    regex=r"^[A-Z0-9-]{1,12}$",
    message="Use 1-12 uppercase letters, numbers, or hyphens.",
)

MAX_BUSINESS_LOGO_BYTES = 2 * 1024 * 1024


def business_logo_upload_to(instance, filename):
    suffix = Path(filename).suffix.lower()
    return f"business-logos/{instance.pk}/{uuid.uuid4().hex}{suffix}"


def validate_business_logo(upload):
    if upload.size > MAX_BUSINESS_LOGO_BYTES:
        raise ValidationError("Business logos must be 2 MB or smaller.")

    position = upload.tell()
    header = upload.read(12)
    upload.seek(position)
    is_png = header.startswith(b"\x89PNG\r\n\x1a\n")
    is_jpeg = header.startswith(b"\xff\xd8\xff")
    if not (is_png or is_jpeg):
        raise ValidationError("Upload a PNG or JPEG business logo.")


def validate_timezone(value):
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValidationError("Enter a valid IANA time zone.") from exc


class WorkspaceQuerySet(models.QuerySet):
    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(
            memberships__user=user,
            memberships__status=Membership.Status.ACTIVE,
        ).distinct()


class Workspace(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_workspaces",
    )

    objects = WorkspaceQuerySet.as_manager()

    class Meta:
        ordering = ("name", "created_at")

    def __str__(self):
        return self.name


class MembershipQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status=Membership.Status.ACTIVE)

    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(user=user)


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        INVITED = "invited", "Invited"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.PROTECT,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="workspace_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    invited_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)

    objects = MembershipQuerySet.as_manager()

    class Meta:
        ordering = ("workspace_id", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "user"),
                name="workspaces_membership_workspace_user_unique",
            ),
            models.UniqueConstraint(
                fields=("workspace",),
                condition=Q(role="owner", status="active"),
                name="workspaces_membership_one_active_owner",
            ),
        ]

    def __str__(self):
        return f"{self.user} - {self.workspace} ({self.role})"


class BusinessQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True, archived_at__isnull=True)

    def for_workspace(self, workspace):
        if workspace is None:
            return self.none()
        return self.filter(workspace=workspace)

    def for_user(self, user):
        if not getattr(user, "is_authenticated", False):
            return self.none()
        return self.filter(
            workspace__memberships__user=user,
            workspace__memberships__status=Membership.Status.ACTIVE,
            workspace__status=Workspace.Status.ACTIVE,
        ).distinct()


class Business(TimeStampedModel):
    class Currency(models.TextChoices):
        USD = "USD", "US Dollar (USD)"
        CAD = "CAD", "Canadian Dollar (CAD)"
        EUR = "EUR", "Euro (EUR)"
        GBP = "GBP", "Pound Sterling (GBP)"
        AUD = "AUD", "Australian Dollar (AUD)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.PROTECT,
        related_name="businesses",
    )
    legal_name = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    owner_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    website = models.URLField(blank=True)
    logo = models.FileField(
        upload_to=business_logo_upload_to,
        validators=[
            FileExtensionValidator(allowed_extensions=("png", "jpg", "jpeg")),
            validate_business_logo,
        ],
        max_length=500,
        blank=True,
    )
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120)
    region = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=30)
    country_code = models.CharField(max_length=2, default="US")
    default_currency = models.CharField(
        max_length=3,
        choices=Currency.choices,
        default=Currency.USD,
    )
    timezone = models.CharField(
        max_length=64,
        default="America/New_York",
        validators=[validate_timezone],
    )
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)

    objects = BusinessQuerySet.as_manager()

    class Meta:
        verbose_name_plural = "businesses"
        ordering = ("display_name", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("workspace",),
                condition=Q(is_active=True, archived_at__isnull=True),
                name="workspaces_business_one_active_per_workspace",
            )
        ]
        indexes = [models.Index(fields=("workspace", "is_active"))]

    def __str__(self):
        return self.display_name


class BusinessSettings(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        Business,
        on_delete=models.PROTECT,
        related_name="settings",
    )
    estimate_prefix = models.CharField(
        max_length=12,
        default="EST-",
        validators=[document_prefix_validator],
    )
    invoice_prefix = models.CharField(
        max_length=12,
        default="INV-",
        validators=[document_prefix_validator],
    )
    default_payment_terms_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MaxValueValidator(365)],
    )
    default_estimate_expiration_days = models.PositiveSmallIntegerField(
        default=30,
        validators=[MaxValueValidator(365)],
    )
    default_tax_rate = models.DecimalField(
        max_digits=7,
        decimal_places=4,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    default_invoice_notes = models.TextField(blank=True)
    default_invoice_terms = models.TextField(blank=True)
    default_estimate_notes = models.TextField(blank=True)
    default_estimate_terms = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "business settings"

    def __str__(self):
        return f"Settings for {self.business}"
