import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import BusinessOwnedModel


class DocumentSnapshot(BusinessOwnedModel):
    estimate = models.OneToOneField(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="document_snapshot",
        blank=True,
        null=True,
    )
    invoice = models.OneToOneField(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="document_snapshot",
        blank=True,
        null=True,
    )
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()
    content_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(estimate__isnull=False, invoice__isnull=True)
                    | Q(estimate__isnull=True, invoice__isnull=False)
                ),
                name="communications_snapshot_exactly_one_document",
            )
        ]

    def save(self, *args, **kwargs):
        if self._state.adding is False:
            raise ValidationError("Document snapshots are immutable.")
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Snapshot and estimate must share a business.")
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Snapshot and invoice must share a business.")

    def __str__(self):
        return f"Snapshot for {self.estimate or self.invoice}"


class PublicDocumentLink(BusinessOwnedModel):
    class Purpose(models.TextChoices):
        VIEW = "view", "View"
        RESPOND = "respond", "View and respond"
        PAY = "pay", "Pay"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="public_links",
        blank=True,
        null=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="public_links",
        blank=True,
        null=True,
    )
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(blank=True, null=True)
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "estimate", "purpose", "revoked_at")),
            models.Index(fields=("business", "invoice", "purpose", "revoked_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(estimate__isnull=False, invoice__isnull=True)
                    | Q(estimate__isnull=True, invoice__isnull=False)
                ),
                name="communications_link_exactly_one_document",
            )
        ]

    @property
    def is_active(self):
        return self.revoked_at is None and self.expires_at > timezone.now()

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Public link and estimate must share a business.")
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Public link and invoice must share a business.")
        if self.invoice_id and self.purpose not in (
            self.Purpose.VIEW,
            self.Purpose.PAY,
        ):
            raise ValidationError("Invoice links support view or pay access only.")


class FileAsset(BusinessOwnedModel):
    class Kind(models.TextChoices):
        ESTIMATE_PDF = "estimate_pdf", "Estimate PDF"
        INVOICE_PDF = "invoice_pdf", "Invoice PDF"
        PAYMENT_RECEIPT = "payment_receipt", "Payment receipt"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="file_assets",
        blank=True,
        null=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="file_assets",
        blank=True,
        null=True,
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="file_assets",
        blank=True,
        null=True,
    )
    snapshot = models.ForeignKey(
        DocumentSnapshot,
        on_delete=models.PROTECT,
        related_name="file_assets",
        blank=True,
        null=True,
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    storage_name = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=100, default="application/pdf")
    byte_size = models.PositiveBigIntegerField()
    content_sha256 = models.CharField(max_length=64)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        estimate__isnull=False,
                        invoice__isnull=True,
                        payment__isnull=True,
                    )
                    | Q(
                        estimate__isnull=True,
                        invoice__isnull=False,
                        payment__isnull=True,
                    )
                    | Q(
                        estimate__isnull=True,
                        invoice__isnull=True,
                        payment__isnull=False,
                    )
                ),
                name="communications_file_exactly_one_target",
            )
        ]

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("File and estimate must share a business.")
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("File and invoice must share a business.")
        if self.payment_id and self.business_id != self.payment.business_id:
            raise ValidationError("File and payment must share a business.")
        if self.snapshot_id and self.business_id != self.snapshot.business_id:
            raise ValidationError("File and snapshot must share a business.")
        if self.snapshot_id:
            if self.estimate_id and self.estimate_id != self.snapshot.estimate_id:
                raise ValidationError("File and snapshot targets must match.")
            if self.invoice_id and self.invoice_id != self.snapshot.invoice_id:
                raise ValidationError("File and snapshot targets must match.")
            if self.payment_id:
                raise ValidationError("Payment receipts do not use document snapshots.")
        expected_target = {
            self.Kind.ESTIMATE_PDF: "estimate",
            self.Kind.INVOICE_PDF: "invoice",
            self.Kind.PAYMENT_RECEIPT: "payment",
        }[self.kind]
        if not getattr(self, f"{expected_target}_id"):
            raise ValidationError(
                f"{self.get_kind_display()} files require a matching {expected_target}."
            )


class EmailDelivery(BusinessOwnedModel):
    class Kind(models.TextChoices):
        ESTIMATE = "estimate", "Estimate"
        INVOICE = "invoice", "Invoice"
        REMINDER = "reminder", "Invoice reminder"
        RECEIPT = "receipt", "Payment receipt"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    estimate = models.ForeignKey(
        "estimates.Estimate",
        on_delete=models.PROTECT,
        related_name="email_deliveries",
        blank=True,
        null=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.PROTECT,
        related_name="email_deliveries",
        blank=True,
        null=True,
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.PROTECT,
        related_name="email_deliveries",
        blank=True,
        null=True,
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ESTIMATE)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )
    sent_at = models.DateTimeField(blank=True, null=True)
    failure_code = models.CharField(max_length=80, blank=True)
    failure_message = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("business", "status", "created_at")),
            models.Index(fields=("business", "kind", "created_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        estimate__isnull=False,
                        invoice__isnull=True,
                        payment__isnull=True,
                    )
                    | Q(
                        estimate__isnull=True,
                        invoice__isnull=False,
                        payment__isnull=True,
                    )
                    | Q(
                        estimate__isnull=True,
                        invoice__isnull=True,
                        payment__isnull=False,
                    )
                ),
                name="communications_delivery_exactly_one_target",
            )
        ]

    def clean(self):
        super().clean()
        if self.estimate_id and self.business_id != self.estimate.business_id:
            raise ValidationError("Delivery and estimate must share a business.")
        if self.invoice_id and self.business_id != self.invoice.business_id:
            raise ValidationError("Delivery and invoice must share a business.")
        if self.payment_id and self.business_id != self.payment.business_id:
            raise ValidationError("Delivery and payment must share a business.")
        expected_target = {
            self.Kind.ESTIMATE: "estimate",
            self.Kind.INVOICE: "invoice",
            self.Kind.REMINDER: "invoice",
            self.Kind.RECEIPT: "payment",
        }[self.kind]
        if not getattr(self, f"{expected_target}_id"):
            raise ValidationError(
                f"{self.get_kind_display()} delivery requires a matching "
                f"{expected_target}."
            )


class Notification(BusinessOwnedModel):
    class Kind(models.TextChoices):
        ESTIMATE_ACCEPTED = "estimate_accepted", "Estimate accepted"
        ESTIMATE_DECLINED = "estimate_declined", "Estimate declined"
        PAYMENT_RECEIVED = "payment_received", "Payment received"
        INVOICE_OVERDUE = "invoice_overdue", "Invoice overdue"
        DELIVERY_FAILED = "delivery_failed", "Delivery failed"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="business_notifications",
    )
    kind = models.CharField(max_length=40, choices=Kind.choices)
    title = models.CharField(max_length=160)
    body = models.CharField(max_length=500)
    target_path = models.CharField(max_length=500, blank=True)
    dedupe_key = models.CharField(max_length=180)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("business", "dedupe_key"),
                name="communications_notification_business_dedupe_unique",
            )
        ]
        indexes = [models.Index(fields=("business", "recipient", "read_at"))]

    def clean(self):
        super().clean()
        if (
            self.recipient_id
            and not self.recipient.memberships.filter(
                workspace=self.business.workspace,
                status="active",
            ).exists()
        ):
            raise ValidationError(
                "Notification recipient must belong to the workspace."
            )

    def __str__(self):
        return self.title


class OutboxEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        "workspaces.Business",
        on_delete=models.PROTECT,
        related_name="outbox_events",
    )
    event_type = models.CharField(max_length=80)
    dedupe_key = models.CharField(max_length=180, unique=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    attempts = models.PositiveIntegerField(default=0)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    last_error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("status", "available_at")),
            models.Index(fields=("business", "status", "available_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="completed", processed_at__isnull=False)
                    | (~Q(status="completed") & Q(processed_at__isnull=True))
                ),
                name="communications_outbox_completion_consistent",
            )
        ]
