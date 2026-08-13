import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from core.models import BusinessOwnedModel


class Payment(BusinessOwnedModel):
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        ONLINE = "online", "Online"

    class Method(models.TextChoices):
        CASH = "cash", "Cash"
        CHECK = "check", "Check"
        ACH = "ach", "ACH"
        CREDIT_CARD = "credit_card", "Credit card"
        VENMO = "venmo", "Venmo"
        PAYPAL = "paypal", "PayPal"
        OTHER = "other", "Other"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    source = models.CharField(
        max_length=20,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    currency = models.CharField(max_length=3)
    invoice_total_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after_snapshot = models.DecimalField(max_digits=14, decimal_places=2)
    paid_on = models.DateField()
    method = models.CharField(max_length=30, choices=Method.choices)
    reference = models.CharField(max_length=120, blank=True)
    note = models.TextField(blank=True)
    provider_payment_id = models.CharField(max_length=255, blank=True, null=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_payments",
        blank=True,
        null=True,
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-paid_on", "-posted_at")
        indexes = [
            models.Index(fields=("business", "invoice", "paid_on")),
            models.Index(fields=("business", "paid_on")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("provider_payment_id",),
                condition=models.Q(provider_payment_id__isnull=False),
                name="payments_payment_provider_id_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(amount__gt=0)
                    & models.Q(invoice_total_snapshot__gte=0)
                    & models.Q(balance_after_snapshot__gte=0)
                ),
                name="payments_payment_amount_positive",
            ),
        ]

    @property
    def reversed_amount(self):
        return sum(
            (reversal.amount for reversal in self.reversals.all()),
            start=self.amount * 0,
        )

    @property
    def net_amount(self):
        return self.amount - self.reversed_amount

    @property
    def effective_status(self):
        if self.reversed_amount == self.amount:
            return "reversed"
        if self.reversed_amount > 0:
            return "partially_reversed"
        return "posted"

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Payment and invoice must share a business.")
        if self.invoice_id and self.currency != self.invoice.currency:
            raise ValidationError("Payment and invoice currencies must match.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Posted payments are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.currency} {self.amount} for {self.invoice}"


class PaymentReversal(BusinessOwnedModel):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="reversals",
    )
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
    )
    reason = models.TextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="recorded_payment_reversals",
        blank=True,
        null=True,
    )
    reversed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-reversed_at",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0),
                name="payments_reversal_amount_positive",
            )
        ]

    def clean(self):
        super().clean()
        if self.payment_id and self.business_id != self.payment.business_id:
            raise ValidationError("Reversal and payment must share a business.")
        if not self.reason.strip():
            raise ValidationError("Enter a reversal reason.")

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Payment reversals are immutable.")
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Reversal for {self.payment}"


class ConnectedAccount(BusinessOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Onboarding pending"
        RESTRICTED = "restricted", "Restricted"
        READY = "ready", "Ready"
        DISABLED = "disabled", "Disabled"

    provider_account_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    details_submitted = models.BooleanField(default=False)
    charges_enabled = models.BooleanField(default=False)
    payouts_enabled = models.BooleanField(default=False)
    requirements_due = models.JSONField(default=list, blank=True)
    disabled_reason = models.CharField(max_length=255, blank=True)
    provider_synced_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("business_id",)
        constraints = [
            models.UniqueConstraint(
                fields=("business",), name="payments_connected_account_business_unique"
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(status="ready")
                    | Q(
                        details_submitted=True,
                        charges_enabled=True,
                        payouts_enabled=True,
                    )
                ),
                name="payments_connected_account_ready_consistent",
            ),
        ]

    @property
    def is_ready(self):
        return self.status == self.Status.READY


class InvoicePaymentAttempt(BusinessOwnedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Creating checkout"
        OPEN = "open", "Awaiting payment"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="online_payment_attempts",
    )
    public_link = models.ForeignKey(
        "communications.PublicDocumentLink",
        on_delete=models.PROTECT,
        related_name="payment_attempts",
    )
    amount = models.DecimalField(
        max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)]
    )
    currency = models.CharField(max_length=3)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    idempotency_key = models.CharField(max_length=255, unique=True)
    provider_checkout_session_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    provider_payment_intent_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )
    checkout_url = models.URLField(max_length=1000, blank=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(blank=True, null=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "invoice", "status")),
            models.Index(fields=("status", "expires_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="payments_attempt_amount_positive"
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="completed", completed_at__isnull=False)
                    | (~Q(status="completed") & Q(completed_at__isnull=True))
                ),
                name="payments_attempt_completion_consistent",
            ),
        ]

    def clean(self):
        super().clean()
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Payment attempt and invoice must share a business.")
        if self.public_link_id and self.business_id != self.public_link.business_id:
            raise ValidationError(
                "Payment attempt and public link must share a business."
            )
        if self.invoice_id and self.currency != self.invoice.currency:
            raise ValidationError("Payment attempt and invoice currencies must match.")


class ConnectWebhookEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        IGNORED = "ignored", "Ignored"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_event_id = models.CharField(max_length=255, unique=True)
    connected_account_id = models.CharField(max_length=255, blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [models.Index(fields=("status", "created_at"))]
