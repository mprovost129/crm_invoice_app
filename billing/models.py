import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class Plan(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=40, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    currency = models.CharField(max_length=3, default="USD")
    monthly_price_cents = models.PositiveIntegerField(default=0)
    annual_price_cents = models.PositiveIntegerField(default=0)
    provider_monthly_price_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    provider_annual_price_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    active_contact_limit = models.PositiveIntegerField(blank=True, null=True)
    monthly_estimate_limit = models.PositiveIntegerField(blank=True, null=True)
    monthly_invoice_limit = models.PositiveIntegerField(blank=True, null=True)
    allow_online_payments = models.BooleanField(default=False)
    allow_custom_branding = models.BooleanField(default=False)
    allow_reminders = models.BooleanField(default=False)
    allow_reporting = models.BooleanField(default=False)
    allow_exports = models.BooleanField(default=False)

    class Meta:
        ordering = ("display_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(active_contact_limit__isnull=True)
                    | Q(active_contact_limit__gt=0)
                ),
                name="billing_plan_contact_limit_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(monthly_estimate_limit__isnull=True)
                    | Q(monthly_estimate_limit__gt=0)
                ),
                name="billing_plan_estimate_limit_positive",
            ),
            models.CheckConstraint(
                condition=(
                    Q(monthly_invoice_limit__isnull=True)
                    | Q(monthly_invoice_limit__gt=0)
                ),
                name="billing_plan_invoice_limit_positive",
            ),
        ]

    @property
    def is_free(self):
        return self.code == "free"

    @property
    def monthly_price_display(self):
        return Decimal(self.monthly_price_cents) / Decimal("100")

    @property
    def annual_price_display(self):
        return Decimal(self.annual_price_cents) / Decimal("100")

    def __str__(self):
        return self.name


class Subscription(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIALING = "trialing", "Trialing"
        PAST_DUE = "past_due", "Past due"
        INCOMPLETE = "incomplete", "Incomplete"
        UNPAID = "unpaid", "Unpaid"
        CANCELED = "canceled", "Canceled"

    class Interval(models.TextChoices):
        NONE = "none", "No billing interval"
        MONTH = "month", "Monthly"
        YEAR = "year", "Annual"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.OneToOneField(
        "workspaces.Workspace",
        on_delete=models.PROTECT,
        related_name="subscription",
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.ACTIVE
    )
    billing_interval = models.CharField(
        max_length=10, choices=Interval.choices, default=Interval.NONE
    )
    provider_customer_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    provider_subscription_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    current_period_end = models.DateTimeField(blank=True, null=True)
    cancel_at_period_end = models.BooleanField(default=False)
    provider_synced_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("workspace_id",)
        indexes = [models.Index(fields=("status", "current_period_end"))]

    @property
    def grants_access(self):
        return self.status in {self.Status.ACTIVE, self.Status.TRIALING}

    def clean(self):
        super().clean()
        if self.plan_id and self.plan.is_free:
            if self.billing_interval != self.Interval.NONE:
                raise ValidationError("Free subscriptions have no billing interval.")

    def __str__(self):
        return f"{self.workspace} - {self.plan}"


class PlatformWebhookEvent(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=120)
    livemode = models.BooleanField(default=False)
    payload = models.JSONField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    attempts = models.PositiveIntegerField(default=0)
    signature_verified_at = models.DateTimeField()
    processed_at = models.DateTimeField(blank=True, null=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("status", "created_at"))]
